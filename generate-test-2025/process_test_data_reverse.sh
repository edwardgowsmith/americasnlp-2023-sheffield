homedir="/users/acp20eg/americas-nlp-baseline"

declare -a langs=("agr" "aym" "bzd" "cni" "ctp" "gn" "guc" "hch" "nah" "oto" "quy" "shp" "tar")
declare -A lang_dict=(
    ["agr"]="agr"
    ["aym"]="ayr"
    ["bzd"]="bzd"
    ["cni"]="cni"
    ["ctp"]="ctp"
    ["gn"]="grn"
    ["guc"]="guc"
    ["hch"]="hch"
    ["nah"]="nah"
    ["oto"]="oto"
    ["quy"]="quy"
    ["shp"]="shp"
    ["tar"]="tar"
)

# Replace characters

for l in "${langs[@]}"
do
    f="${data_dir}/inputs/xx-es/${l}/test.${l}-es.src"
    sed -i "s/\“/@\"/g" $f
    sed -i "s/\”/調\"/g" $f
    sed -i "s/\“/付\"/g" $f
    sed -i "s/\’/혼\'/g" $f
    sed -i "s/\‘/ච\'/g" $f
    sed -i "s/\—/완\-/g" $f
    sed -i "s/\–/罪\-/g" $f
    sed -i "s/\«/\<\</g" $f
    sed -i "s/\»/\>\>/g" $f
    sed -i "s/\‚/\,/g" $f

    cat $f | python $homedir/fairseq/scripts/spm_encode.py \
    --model $homedir/evaluation_v3/NLLB-inference/preprocess/flores200_sacrebleu_tokenizer_spm.model \
    > ${data_dir}/test-data-reverse/test.${lang_dict[$l]}_Latn-spa_Latn.${lang_dict[$l]}_Latn

    mkdir ${data_dir}/data-bin-test-reverse/${lang_dict[$l]}-spa_Latn

    fairseq-preprocess --source-lang ${lang_dict[$l]}_Latn --target-lang spa_Latn  \
    --only-source \
    --testpref ${data_dir}/test-data-reverse/test.${lang_dict[$l]}_Latn-spa_Latn \
    --joined-dictionary	\
    --srcdict $homedir/evaluation_v3/NLLB-inference/dictionary.txt \
    --destdir ${data_dir}/data-bin-test-reverse/spa_Latn-${lang_dict[$l]}/ \
    --workers 10

done

cp ${data_dir}/data-bin-test-reverse/*/*.bin ${data_dir}/data-bin-test-combined-reverse
cp ${data_dir}/data-bin-test-reverse/*/*.idx ${data_dir}/data-bin-test-combined-reverse
cp ${data_dir}/data-bin-test-reverse/*/dict.*.txt ${data_dir}/data-bin-test-combined-reverse