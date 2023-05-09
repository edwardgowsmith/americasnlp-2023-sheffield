
ckp=nllb-3.3B/checkpoint.pt
databin=data-bin/combined
root=evaluation_v3/NLLB-inference


export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
fairseq-train $databin --lang-pairs eng_Latn-quy_Latn,spa_Latn-quy_Latn \
    --eval-lang-pairs spa_Latn-quy_Latn \
    --encoder-normalize-before --decoder-normalize-before \
    --arch transformer \
    --share-all-embeddings \
    --encoder-layers 24 --encoder-attention-heads 16 \
    --decoder-layers 24 --decoder-attention-heads 16 \
    --encoder-embed-dim 2048 --decoder-embed-dim 2048 \
    --encoder-ffn-embed-dim 8192 --decoder-ffn-embed-dim 8192 \
    --task translation_multi_simple_epoch \
    --finetune-from-model $ckp \
    --optimizer adam --adam-betas '(0.9, 0.98)' --clip-norm 1e-6 \
    --lr 0.01 --lr-scheduler inverse_sqrt --warmup-updates 10000 \
    --max-update 800000 \
    --validate-interval-updates 20000 \
    --save-interval-updates 20000 \
    --dropout 0.3 --weight-decay 0.0001 \
    --criterion label_smoothed_cross_entropy --label-smoothing 0.1 \
    --batch-size 2 \
    --update-freq 1 \
    --fp16 \
    --fixed-dictionary $root/dictionary.txt \
    --decoder-langtok --encoder-langtok src \
    --langs $(cat $root/langs_extra.txt) \
    --eval-bleu \
    --eval-bleu-args '{"beam": 5, "max_len_a": 1.2, "max_len_b": 10}' \
    --eval-bleu-detok space \
    --eval-bleu-remove-bpe \
    --sentencepiece-model NLLB-inference/preprocess/flores200_sacrebleu_tokenizer_spm.model \
    --best-checkpoint-metric chrf \
    --scoring chrf \
    --add-data-source-prefix-tags 2>&1

