tlang=spa
ckp_dir={checkpoint_directory}
ckp=checkpoint11.pt 
ckp=${ckp_dir}${ckp}
databin={databin_directory}
root={rootdirectory}

out=dev-translation-reverse/
mkdir $out

for slang in quy ayr grn cni ctp oto nah tar shp hch bzd agr guc
do
fairseq-generate $databin -s ${slang}_Latn -t ${tlang}_Latn \
    --path $ckp --batch-size 128 \
    --beam 4 --lenpen 1.0 \
    --gen-subset valid \
    --fixed-dictionary ${root}/dictionary.txt \
    --task translation_multi_simple_epoch \
    --decoder-langtok --encoder-langtok src \
    --langs $(cat langs_extra.txt) \
    --lang-pairs ${slang}_Latn-${tlang}_Latn \
    --remove-bpe=sentencepiece \
    --add-data-source-prefix-tags 2>&1 > ${out}/${slang}.out \
    --skip-invalid-size-inputs-valid-test

sed -i "s/@\"/\"/g" ${out}/${slang}.out
sed -i "s/調\"/\"/g" ${out}/${slang}.out
sed -i "s/付\"/\"/g" ${out}/${slang}.out
sed -i "s/혼'/'/g" ${out}/${slang}.out
sed -i "s/ච'/'/g" ${out}/${slang}.out
sed -i "s/완-/-/g" ${out}/${slang}.out
sed -i "s/罪-/-/g" ${out}/${slang}.out
sed -i "s/«/<</g" ${out}/${slang}.out
sed -i "s/»/>>/g" ${out}/${slang}.out
sed -i "s/‚/,/g" ${out}/${slang}.out
sed -i "s/ ' /'/g" ${out}/${slang}.out

echo $slang
lang=${slang}_Latn
cat ${out}/${slang}.out | grep ^H | LC_ALL=C sort -V | cut -f3 > ${out}/${slang}.hyp

done