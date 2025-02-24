# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import datetime
import itertools
import logging
import time
import json
import numpy as np
import torch
from argparse import Namespace

from fairseq import utils, metrics

from fairseq.data import (
    FairseqDataset,
    LanguagePairDataset,
    ListDataset,
    data_utils,
    iterators,
)
from fairseq.data.multilingual.multilingual_data_manager import (
    MultilingualDatasetManager,
)
from fairseq.data.multilingual.multilingual_utils import LangTokStyle, get_lang_tok
from fairseq.data.multilingual.sampling_method import SamplingMethod
from fairseq.tasks import LegacyFairseqTask, register_task
from fairseq.utils import FileContentsAction


###
def get_time_gap(s, e):
    return (
        datetime.datetime.fromtimestamp(e) - datetime.datetime.fromtimestamp(s)
    ).__str__()


###

EVAL_BLEU_ORDER = 4
logger = logging.getLogger(__name__)


@register_task("translation_multi_simple_epoch")
class TranslationMultiSimpleEpochTask(LegacyFairseqTask):
    """
    Translate from one (source) language to another (target) language.

    Args:
        langs (List[str]): a list of languages that are being supported
        dicts (Dict[str, fairseq.data.Dictionary]): mapping from supported languages to their dictionaries
        training (bool): whether the task should be configured for training or not

    .. note::

        The translation task is compatible with :mod:`fairseq-train`,
        :mod:`fairseq-generate` and :mod:`fairseq-interactive`.

    The translation task provides the following additional command-line
    arguments:

    .. argparse::
        :ref: fairseq.tasks.translation_parser
        :prog:
    """

    @staticmethod
    def add_args(parser):
        """Add task-specific arguments to the parser."""
        # fmt: off
        parser.add_argument('-s', '--source-lang', default=None, metavar='SRC',
                            help='inference source language')
        parser.add_argument('-t', '--target-lang', default=None, metavar='TARGET',
                            help='inference target language')
        parser.add_argument('--lang-pairs', default=None, metavar='PAIRS',
                            help='comma-separated list of language pairs (in training order): en-de,en-fr,de-fr',
                            action=FileContentsAction)
        # parser.add_argument('--eval-lang-pairs', default=None, metavar='PAIRS',
        #                     help='comma-separated list of eval language pairs',
        #                     action=FileContentsAction)
        parser.add_argument('--keep-inference-langtok', action='store_true',
                            help='keep language tokens in inference output (e.g. for analysis or debugging)')
        parser.add_argument('--one-dataset-per-batch', action='store_true',
                            help='limit each minibatch to one sub-dataset (typically lang direction)')
        parser.add_argument('--eval-bleu', action='store_true',
                            help='evaluation with BLEU scores')
        parser.add_argument('--eval-bleu-detok', type=str, default="space",
                            help='detokenize before computing BLEU (e.g., "moses"); '
                                 'required if using --eval-bleu; use "space" to '
                                 'disable detokenization; see fairseq.data.encoders '
                                 'for other options')
        parser.add_argument('--eval-bleu-detok-args', type=str, metavar='JSON',
                            help='args for building the tokenizer, if needed')
        parser.add_argument('--eval-tokenized-bleu', action='store_true', default=False,
                            help='compute tokenized BLEU instead of sacrebleu')
        parser.add_argument('--eval-bleu-remove-bpe', nargs='?', const='@@ ', default=None,
                            help='remove BPE before computing BLEU')
        parser.add_argument('--eval-bleu-args', type=str, metavar='JSON',
                            help='generation args for BLUE scoring, '
                                 'e.g., \'{"beam": 4, "lenpen": 0.6}\'')
        parser.add_argument('--eval-bleu-print-samples', action='store_true',
                            help='print sample generations during validation')
        parser.add_argument('--sentencepiece-model', type=str, default=None)
        parser.add_argument('--freeze-encoder', action='store_true')
        parser.add_argument('--freeze-decoder', action='store_true')
        parser.add_argument('--unfreeze-layers', type=int, default=None)

        SamplingMethod.add_arguments(parser)
        MultilingualDatasetManager.add_args(parser)
        # fmt: on

    def __init__(self, args, langs, dicts, training):
        super().__init__(args)
        self.langs = langs
        self.dicts = dicts
        self.training = training
        if training:
            self.lang_pairs = args.lang_pairs
        else:
            self.lang_pairs = ["{}-{}".format(args.source_lang, args.target_lang)]
        # eval_lang_pairs for multilingual translation is usually all of the
        # lang_pairs. However for other multitask settings or when we want to
        # optimize for certain languages we want to use a different subset. Thus
        # the eval_lang_pairs class variable is provided for classes that extend
        # this class.
        self.eval_lang_pairs = args.eval_lang_pairs
        print("eval_lang_pairs")
        print(args.eval_lang_pairs)
        # model_lang_pairs will be used to build encoder-decoder model pairs in
        # models.build_model(). This allows multitask type of sub-class can
        # build models other than the input lang_pairs
        self.model_lang_pairs = self.lang_pairs
        self.source_langs = [d.split("-")[0] for d in self.lang_pairs]
        self.target_langs = [d.split("-")[1] for d in self.lang_pairs]
        self.check_dicts(self.dicts, self.source_langs, self.target_langs)

        self.sampling_method = SamplingMethod.build_sampler(args, self)
        self.data_manager = MultilingualDatasetManager.setup_data_manager(
            args, self.lang_pairs, langs, dicts, self.sampling_method
        )
        self.lang_idx = self.get_lang_idx()
        self.one_dataset_per_batch = getattr(args, "one_dataset_per_batch", False)
        if getattr(args, "sentencepiece_model", False):
                import sentencepiece as spm
                self.tokenizer = spm.SentencePieceProcessor(getattr(args, "sentencepiece_model", None))
                # print("tokenizer")
                # print(self.tokenizer)
        else:
            self.tokenizer = None

    def get_lang_idx(self):
        lang_idx = torch.zeros(len(self.langs) + 1, dtype=torch.int32)
        # idx 0 for non-matching prefix tokens
        lang_idx[0] = -1
        for i, lang in enumerate(self.langs):
            lang_tok = get_lang_tok(lang, LangTokStyle.multilingual.value)
            lang_idx[i + 1] = MultilingualDatasetManager.get_langtok_index(
                lang_tok, self.source_dictionary
            )
        return lang_idx

    def check_dicts(self, dicts, source_langs, target_langs):
        if self.args.source_dict is not None or self.args.target_dict is not None:
            # no need to check whether the source side and target side are sharing dictionaries
            return
        src_dict = dicts[source_langs[0]]
        tgt_dict = dicts[target_langs[0]]
        for src_lang in source_langs:
            assert (
                src_dict == dicts[src_lang]
            ), "Diffrent dictionary are specified for different source languages; "
            "TranslationMultiSimpleEpochTask only supports one shared dictionary across all source languages"
        for tgt_lang in target_langs:
            assert (
                tgt_dict == dicts[tgt_lang]
            ), "Diffrent dictionary are specified for different target languages; "
            "TranslationMultiSimpleEpochTask only supports one shared dictionary across all target languages"

    @classmethod
    def setup_task(cls, args, **kwargs):
        if getattr(args, "train_subset", None) is not None:
            if not all(s.startswith("train") for s in args.train_subset.split(",")):
                raise ValueError('Train splits should be named like "train*".')

        langs, dicts, training = MultilingualDatasetManager.prepare(
            cls.load_dictionary, args, **kwargs
        )
        return cls(args, langs, dicts, training)

    def has_sharded_data(self, split):
        return self.data_manager.has_sharded_data(split)

    def load_dataset(self, split, epoch=1, combine=False, **kwargs):
        """Load a given dataset split.

        Args:
            split (str): name of the split (e.g., train, valid, test)
        """
        if split in self.datasets:
            dataset = self.datasets[split]
            if self.has_sharded_data(split):
                if self.args.virtual_epoch_size is not None:
                    if dataset.load_next_shard:
                        shard_epoch = dataset.shard_epoch
                    else:
                        # no need to load next shard so skip loading
                        # also this avoid always loading from beginning of the data
                        return
                else:
                    shard_epoch = epoch
        else:
            # estimate the shard epoch from virtual data size and virtual epoch size
            shard_epoch = self.data_manager.estimate_global_pass_epoch(epoch)
        logger.info(f"loading data for {split} epoch={epoch}/{shard_epoch}")
        logger.info(f"mem usage: {data_utils.get_mem_usage()}")
        if split in self.datasets:
            del self.datasets[split]
            logger.info("old dataset deleted manually")
            logger.info(f"mem usage: {data_utils.get_mem_usage()}")
        split_datasets = self.data_manager.load_dataset(
            split,
            self.training,
            epoch=epoch,
            combine=combine,
            shard_epoch=shard_epoch,
            **kwargs,
        )
        for split, dataset in split_datasets.items():
            self.datasets[split] = dataset

    def build_dataset_for_inference(self, src_tokens, src_lengths, constraints=None):
        if constraints is not None:
            raise NotImplementedError(
                "Constrained decoding with the multilingual_translation task is not supported"
            )

        src_data = ListDataset(src_tokens, src_lengths)
        dataset = LanguagePairDataset(src_data, src_lengths, self.source_dictionary)
        src_langtok_spec, tgt_langtok_spec = self.args.langtoks["main"]
        if self.args.lang_tok_replacing_bos_eos:
            dataset = self.data_manager.alter_dataset_langtok(
                dataset,
                src_eos=self.source_dictionary.eos(),
                src_lang=self.args.source_lang,
                tgt_eos=self.target_dictionary.eos(),
                tgt_lang=self.args.target_lang,
                src_langtok_spec=src_langtok_spec,
                tgt_langtok_spec=tgt_langtok_spec,
            )
        else:
            dataset.src = self.data_manager.src_dataset_transform_func(
                self.args.source_lang,
                self.args.target_lang,
                dataset=dataset.src,
                spec=src_langtok_spec,
            )
        return dataset

    def build_generator(
        self,
        models,
        args,
        seq_gen_cls=None,
        extra_gen_cls_kwargs=None,
        lang=None,
    ):
        if not getattr(args, "keep_inference_langtok", False):
            _, tgt_langtok_spec = self.args.langtoks["main"]
            if tgt_langtok_spec:
                if lang:
                    target_lang = lang
                else:
                    target_lang = self.args.target_lang
                    
                tgt_lang_tok = self.data_manager.get_decoder_langtok(
                    target_lang, tgt_langtok_spec
                )
                extra_gen_cls_kwargs = extra_gen_cls_kwargs or {}
                extra_gen_cls_kwargs["symbols_to_strip_from_output"] = {tgt_lang_tok}

        return super().build_generator(
            models, args, seq_gen_cls=None, extra_gen_cls_kwargs=extra_gen_cls_kwargs
        )

    def build_model(self, args, from_checkpoint=False):
        model = super().build_model(args, from_checkpoint)
        if args.freeze_encoder:
            for name,param in model.encoder.named_parameters():
                param.requires_grad = False
        if args.freeze_decoder:
            for name,param in model.decoder.named_parameters():
                param.requires_grad = False
        if args.unfreeze_layers:
            for name,param in model.encoder.named_parameters():
                logger.info(f"freezing parameter {name}")
                param.requires_grad = False
            layers = range(args.decoder_layers-args.unfreeze_layers)
            for name,param in model.decoder.named_parameters():
                for l in layers:
                    if "layers."+str(l)+"." in name:
                        logger.info(f"freezing parameter {name}")
                        param.requires_grad = False
        return model

    def valid_step(self, sample, model, criterion):
        model.eval()
        with torch.no_grad():
            from collections import defaultdict
            toks = sample["target"][0]
            s = self.data_manager.get_target_dictionary("quy_Latn").string(
                toks.int().cpu(),
                self.args.eval_bleu_remove_bpe,
                unk_string=("UNKNOWNTOKENINHYP"),
            )
            lang_tok = s.split()[0]
            lang = lang_tok.strip("__")

            loss, sample_size, logging_dict = super().valid_step(sample, model, criterion)
            logging_output = defaultdict(float)
            for k in logging_dict:
                logging_output[k] += logging_dict[k]

            if self.args.eval_bleu:
                gen_args = json.loads(getattr(self.args, "eval_bleu_args", "{}") or "{}")
                sequence_generator = self.build_generator(
                    [model], Namespace(**gen_args), lang=lang
                )
                bleu, chrf = self._inference_with_bleu(sequence_generator, sample, model, lang=lang)
                # print("chrf")
                # print(chrf)
                logging_output["_bleu_sys_len"] += bleu.sys_len
                logging_output["_bleu_ref_len"] += bleu.ref_len
                logging_output["_chrf"] += chrf.score
                # we split counts into separate entries so that they can be
                # summed efficiently across workers using fast-stat-sync
                assert len(bleu.counts) == EVAL_BLEU_ORDER
                for i in range(EVAL_BLEU_ORDER):
                    logging_output["_bleu_counts_" + str(i)] += bleu.counts[i]
                    logging_output["_bleu_totals_" + str(i)] += bleu.totals[i]
                
        return loss, sample_size, logging_output

    def _inference_with_bleu(self, generator, sample, model, lang=None):
        import sacrebleu

        def decode(toks, escape_unk=False):
            s = self.data_manager.get_target_dictionary(lang).string(
                toks.int().cpu(),
                self.args.eval_bleu_remove_bpe,
                # The default unknown string in fairseq is `<unk>`, but
                # this is tokenized by sacrebleu as `< unk >`, inflating
                # BLEU scores. Instead, we use a somewhat more verbose
                # alternative that is unlikely to appear in the real
                # reference, but doesn't get split into multiple tokens.
                unk_string=("UNKNOWNTOKENINREF" if escape_unk else "UNKNOWNTOKENINHYP"),
            )
            if self.tokenizer:
                s = self.tokenizer.decode(s.split()[1:])

            return s

        gen_out = self.inference_step(generator, [model], sample, prefix_tokens=None, lang=lang)
        hyps, refs = [], []
        for i in range(len(gen_out)):
            hyps.append(decode(gen_out[i][0]["tokens"]))
            refs.append(
                decode(
                    utils.strip_pad(sample["target"][i], self.data_manager.get_target_dictionary(lang).pad()),
                    escape_unk=True,  # don't count <unk> as matches to the hypo
                )
            )
        if self.args.eval_bleu_print_samples:
            logger.info("example hypothesis: " + hyps[0])
            logger.info("example reference: " + refs[0])
        if self.args.eval_tokenized_bleu:
            return sacrebleu.corpus_bleu(hyps, [refs], tokenize="none"), sacrebleu.corpus_chrf(hyps, [refs], tokenize="none")
        else:
            return sacrebleu.corpus_bleu(hyps, [refs]), sacrebleu.corpus_chrf(hyps, [refs], word_order=2)

    def inference_step(
        self, generator, models, sample, prefix_tokens=None, constraints=None, lang=None,
    ):
        with torch.no_grad():
            _, tgt_langtok_spec = self.args.langtoks["main"]
            if lang:    
                target_lang = lang
            else:
                target_lang = self.args.target_lang
            if not self.args.lang_tok_replacing_bos_eos:
                if prefix_tokens is None and tgt_langtok_spec:
                    tgt_lang_tok = self.data_manager.get_decoder_langtok(
                        target_lang, tgt_langtok_spec
                    )
                    src_tokens = sample["net_input"]["src_tokens"]
                    bsz = src_tokens.size(0)
                    prefix_tokens = (
                        torch.LongTensor([[tgt_lang_tok]]).expand(bsz, 1).to(src_tokens)
                    )
                return generator.generate(
                    models,
                    sample,
                    prefix_tokens=prefix_tokens,
                    constraints=constraints,
                )
            else:
                return generator.generate(
                    models,
                    sample,
                    prefix_tokens=prefix_tokens,
                    bos_token=self.data_manager.get_decoder_langtok(
                        self.args.target_lang, tgt_langtok_spec
                    )
                    if tgt_langtok_spec
                    else self.target_dictionary.eos(),
                )

    def reduce_metrics(self, logging_outputs, criterion):
        with metrics.aggregate():
            # pass 'sample_size', 'nsentences', 'ntokens' stats to fairseq_task
            super().reduce_metrics(logging_outputs, criterion)
            for k in ["sample_size", "nsentences", "ntokens"]:
                metrics.log_scalar(k, sum(l[k] for l in logging_outputs))

            if self.args.eval_bleu:
                
                def sum_logs(key):
                    return sum(log.get(key, 0) for log in logging_outputs)


                chrf_scores = []

                chrf_scores.append(sum_logs("_chrf"))
                metrics.log_scalar(f"chrf", np.array(chrf_scores))

                counts, totals = [], []
                for i in range(EVAL_BLEU_ORDER):
                    counts.append(sum_logs(f"_bleu_counts_" + str(i)))
                    totals.append(sum_logs(f"_bleu_totals_" + str(i)))

                if max(totals) > 0:
                    # log counts as numpy arrays -- log_scalar will sum them correctly
                    metrics.log_scalar(f"_bleu_counts", np.array(counts))
                    metrics.log_scalar(f"_bleu_totals", np.array(totals))
                    metrics.log_scalar(f"_bleu_sys_len", sum_logs(f"_bleu_sys_len"))
                    metrics.log_scalar(f"_bleu_ref_len", sum_logs(f"_bleu_ref_len"))

                    def compute_bleu_lang_pair(meters):
                        import inspect
                        import sacrebleu
                        from sacrebleu.metrics import BLEU

                        fn_sig = inspect.getfullargspec(BLEU.compute_bleu)[0]
                        if "smooth_method" in fn_sig:
                            smooth = {"smooth_method": "exp"}
                        else:
                            smooth = {"smooth": "exp"}
                        bleu = BLEU.compute_bleu(
                            correct=meters[f"_bleu_counts"].sum.astype(int),
                            total=meters[f"_bleu_totals"].sum.astype(int),
                            sys_len=int(meters[f"_bleu_sys_len"].sum),
                            ref_len=int(meters[f"_bleu_ref_len"].sum),
                            **smooth
                        )
                        return round(bleu.score, 5)

                    import functools

                    metrics.log_derived(f"bleu", compute_bleu_lang_pair)

    def max_positions(self):
        """Return the max sentence length allowed by the task."""
        return (self.args.max_source_positions, self.args.max_target_positions)

    @property
    def source_dictionary(self):
        return self.data_manager.get_source_dictionary(self.source_langs[0])

    @property
    def target_dictionary(self):
        return self.data_manager.get_target_dictionary(self.target_langs[0])

    def create_batch_sampler_func(
        self,
        max_positions,
        ignore_invalid_inputs,
        max_tokens,
        max_sentences,
        required_batch_size_multiple=1,
        seed=1,
    ):
        def construct_batch_sampler(dataset, epoch):
            splits = [
                s for s, _ in self.datasets.items() if self.datasets[s] == dataset
            ]
            split = splits[0] if len(splits) > 0 else None
            # NEW implementation
            if epoch is not None:
                # initialize the dataset with the correct starting epoch
                dataset.set_epoch(epoch)

            # get indices ordered by example size
            start_time = time.time()
            logger.info(f"start batch sampler: mem usage: {data_utils.get_mem_usage()}")

            with data_utils.numpy_seed(seed):
                if self.one_dataset_per_batch:
                    ordered_indices_list = dataset.ordered_indices_per_dataset()
                else:
                    ordered_indices_list = [dataset.ordered_indices()]

            # get batches constructed from each underlying dataset to concatenate
            subdataset_sampler_list = []
            for ds_idx, indices in enumerate(ordered_indices_list):
                if self.one_dataset_per_batch:
                    log_tag = f"[{split}] [{ds_idx}]"
                else:
                    log_tag = f"[{split}]"
                logger.info(
                    f"{log_tag} @batch_sampler order indices time: {get_time_gap(start_time, time.time())}"
                )
                logger.info(f"mem usage: {data_utils.get_mem_usage()}")

                # filter examples that are too large
                if max_positions is not None and split is not None:
                    my_time = time.time()
                    indices = self.filter_indices_by_size(
                        indices, dataset, max_positions, ignore_invalid_inputs
                    )
                    logger.info(
                        f"{log_tag} @batch_sampler filter_by_size time: {get_time_gap(my_time, time.time())}"
                    )
                    logger.info(f"mem usage: {data_utils.get_mem_usage()}")

                # create mini-batches with given size constraints
                my_time = time.time()
                batch_sampler = dataset.batch_by_size(
                    indices,
                    max_tokens=max_tokens,
                    max_sentences=max_sentences,
                    required_batch_size_multiple=required_batch_size_multiple,
                )
                subdataset_sampler_list.append(batch_sampler)

                end_time = time.time()
                logger.info(
                    f"{log_tag} @batch_sampler batch_by_size time: {get_time_gap(my_time, end_time)}"
                )
                logger.info(
                    f"{log_tag} per epoch batch_sampler set-up time: {get_time_gap(start_time, end_time)}"
                )
                logger.info(f"mem usage: {data_utils.get_mem_usage()}")

            combined_batch_sampler = itertools.chain(*subdataset_sampler_list)
            return combined_batch_sampler

        return construct_batch_sampler

    # we need to override get_batch_iterator because we want to reset the epoch iterator each time
    def get_batch_iterator(
        self,
        dataset,
        max_tokens=None,
        max_sentences=None,
        max_positions=None,
        ignore_invalid_inputs=False,
        required_batch_size_multiple=1,
        seed=1,
        num_shards=1,
        shard_id=0,
        num_workers=0,
        epoch=1,
        data_buffer_size=0,
        disable_iterator_cache=False,
        skip_remainder_batch=False,
        grouped_shuffling=False,
        update_epoch_batch_itr=False,
    ):
        """
        Get an iterator that yields batches of data from the given dataset.

        Args:
            dataset (~fairseq.data.FairseqDataset): dataset to batch
            max_tokens (int, optional): max number of tokens in each batch
                (default: None).
            max_sentences (int, optional): max number of sentences in each
                batch (default: None).
            max_positions (optional): max sentence length supported by the
                model (default: None).
            ignore_invalid_inputs (bool, optional): don't raise Exception for
                sentences that are too long (default: False).
            required_batch_size_multiple (int, optional): require batch size to
                be a multiple of N (default: 1).
            seed (int, optional): seed for random number generator for
                reproducibility (default: 1).
            num_shards (int, optional): shard the data iterator into N
                shards (default: 1).
            shard_id (int, optional): which shard of the data iterator to
                return (default: 0).
            num_workers (int, optional): how many subprocesses to use for data
                loading. 0 means the data will be loaded in the main process
                (default: 0).
            epoch (int, optional): the epoch to start the iterator from
                (default: 0).
            data_buffer_size (int, optional): number of batches to
                preload (default: 0).
            disable_iterator_cache (bool, optional): don't cache the
                EpochBatchIterator (ignores `FairseqTask::can_reuse_epoch_itr`)
                (default: False).
            skip_remainder_batch (bool, optional): if set, discard the last
                batch in each training epoch, as the last batch is often smaller than
                    local_batch_size * distributed_word_size (default: ``True``).
            grouped_shuffling (bool, optional): group batches with each groups
                containing num_shards batches and shuffle groups. Reduces difference
                between sequence lengths among workers for batches sorted by length.
            update_epoch_batch_itr (bool optional): if true then donot use the cached
                batch iterator for the epoch

        Returns:
            ~fairseq.iterators.EpochBatchIterator: a batched iterator over the
                given dataset split
        """
        # initialize the dataset with the correct starting epoch
        assert isinstance(dataset, FairseqDataset)
        if dataset in self.dataset_to_epoch_iter:
            return self.dataset_to_epoch_iter[dataset]
        if self.args.sampling_method == "RoundRobin":
            batch_iter = super().get_batch_iterator(
                dataset,
                max_tokens=max_tokens,
                max_sentences=max_sentences,
                max_positions=max_positions,
                ignore_invalid_inputs=ignore_invalid_inputs,
                required_batch_size_multiple=required_batch_size_multiple,
                seed=seed,
                num_shards=num_shards,
                shard_id=shard_id,
                num_workers=num_workers,
                epoch=epoch,
                data_buffer_size=data_buffer_size,
                disable_iterator_cache=disable_iterator_cache,
                skip_remainder_batch=skip_remainder_batch,
                update_epoch_batch_itr=update_epoch_batch_itr,
            )
            self.dataset_to_epoch_iter[dataset] = batch_iter
            return batch_iter

        construct_batch_sampler = self.create_batch_sampler_func(
            max_positions,
            ignore_invalid_inputs,
            max_tokens,
            max_sentences,
            required_batch_size_multiple=required_batch_size_multiple,
            seed=seed,
        )

        epoch_iter = iterators.EpochBatchIterator(
            dataset=dataset,
            collate_fn=dataset.collater,
            batch_sampler=construct_batch_sampler,
            seed=seed,
            num_shards=num_shards,
            shard_id=shard_id,
            num_workers=num_workers,
            epoch=epoch,
            skip_remainder_batch=skip_remainder_batch,
        )
        return epoch_iter
