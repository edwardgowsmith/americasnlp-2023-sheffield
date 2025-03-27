databin={databin}
root={root}
ckp={checkpoint_directory}
savedir={savedir}

export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
fairseq-train $databin --lang-pairs grn_Latn-eng_Latn,quy_Latn-eng_Latn,ayr_Latn-eng_Latn,quy_Latn-spa_Latn,ayr_Latn-spa_Latn,grn_Latn-spa_Latn,cni_Latn-spa_Latn,ctp_Latn-eng_Latn,ctp_Latn-spa_Latn,oto_Latn-spa_Latn,nah_Latn-spa_Latn,tar_Latn-spa_Latn,shp_Latn-spa_Latn,hch_Latn-spa_Latn,bzd_Latn-spa_Latn,agr_Latn-spa_Latn,guc_Latn-spa_Latn \
    --eval-lang-pairs quy_Latn-spa_Latn,ayr_Latn-spa_Latn,grn_Latn-spa_Latn,cni_Latn-spa_Latn,ctp_Latn-spa_Latn,oto_Latn-spa_Latn,nah_Latn-spa_Latn,tar_Latn-spa_Latn,shp_Latn-spa_Latn,hch_Latn-spa_Latn,bzd_Latn-spa_Latn,agr_Latn-spa_Latn,guc_Latn-spa_Latn \
    --encoder-normalize-before --decoder-normalize-before \
    --arch transformer \
    --share-all-embeddings \
    --sampling-method "temperature" \
    --sampling-temperature 3 \
    --encoder-layers 24 --encoder-attention-heads 16 \
    --decoder-layers 24 --decoder-attention-heads 16 \
    --encoder-embed-dim 1024 --decoder-embed-dim 1024 \
    --encoder-ffn-embed-dim 8192 --decoder-ffn-embed-dim 8192 \
    --task translation_multi_simple_epoch \
    --finetune-from-model $ckp \
    --optimizer adam --adam-betas '(0.9, 0.98)' --clip-norm 1e-6 \
    --lr 0.01 --lr-scheduler inverse_sqrt --warmup-updates 10000 \
    --max-update 1000000 \
    --validate-interval-updates 40000 \
    --save-interval-updates 40000 \
    --dropout 0.3 --weight-decay 0.0001 \
    --criterion label_smoothed_cross_entropy --label-smoothing 0.1 \
    --batch-size 16 \
    --update-freq 1 \
    --fp16 \
    --seed 1 \
    --fixed-dictionary $root/dictionary.txt \
    --decoder-langtok --encoder-langtok src \
    --langs $(cat langs_extra.txt) \
    --eval-bleu \
    --eval-bleu-args '{"beam": 5, "max_len_a": 1.2, "max_len_b": 10}' \
    --eval-bleu-detok space \
    --eval-bleu-remove-bpe \
    --sentencepiece-model $root/preprocess/flores200_sacrebleu_tokenizer_spm.model \
    --save-dir $savedir \
    --best-checkpoint-metric chrf \
    --scoring chrf \
    --skip-invalid-size-inputs-valid-test \
    --add-data-source-prefix-tags 2>&1

