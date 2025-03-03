slang=spa_Latn
ckp_dir={CKP_DIR}
ckp=checkpoint_12_1000000.pt
ckp=${ckp_dir}${ckp}

data_bin_dir={DATA_BIN_DIR}
out=dev-translation/
mkdir $out

for tlang in quy ayr grn cni ctp oto nah tar shp hch bzd
do
fairseq-generate $data_bin_dir -s $slang -t ${tlang}_Latn \
    --path $ckp --batch-size 128 \
    --beam 4 --lenpen 1.0 \
    --gen-subset dev \
    --fixed-dictionary ../NLLB-inference/dictionary.txt \
    --task translation_multi_simple_epoch \
    --decoder-langtok --encoder-langtok src \
    --langs $(cat ../NLLB-inference/langs_extra.txt) \
    --lang-pairs $slang-${tlang}_Latn \
    --remove-bpe=sentencepiece \
    --add-data-source-prefix-tags 2>&1 > ${out}/${tlang}.out

sed -i "s/@\"/\"/g" ${out}/${tlang}.out
sed -i "s/調\"/\"/g" ${out}/${tlang}.out
sed -i "s/付\"/\"/g" ${out}/${tlang}.out
sed -i "s/혼'/'/g" ${out}/${tlang}.out
sed -i "s/ච'/'/g" ${out}/${tlang}.out
sed -i "s/완-/-/g" ${out}/${tlang}.out
sed -i "s/罪-/-/g" ${out}/${tlang}.out
sed -i "s/«/<</g" ${out}/${tlang}.out
sed -i "s/»/>>/g" ${out}/${tlang}.out
sed -i "s/‚/,/g" ${out}/${tlang}.out
sed -i "s/ ' /'/g" ${out}/${tlang}.out

echo $tlang
lang=${tlang}_Latn
cat ${out}/${tlang}.out | grep ^H | LC_ALL=C sort -V | cut -f3 > ${out}/${tlang}.hyp

done