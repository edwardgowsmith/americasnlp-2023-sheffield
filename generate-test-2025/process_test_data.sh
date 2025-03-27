homedir={home_dir}
data_dir={data_dir}

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
    f="${data_dir}/inputs/es-xx/${l}/test.es-${l}.src"
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
    > ${data_dir}/test-data/test.spa_Latn-${lang_dict[$l]}_Latn.spa_Latn

    mkdir ${data_dir}/data-bin-test/spa_Latn-${lang_dict[$l]}/ 

    fairseq-preprocess --source-lang spa_Latn --target-lang ${lang_dict[$l]}_Latn \
    --only-source \
    --testpref ${data_dir}/test-data/test.spa_Latn-${lang_dict[$l]}_Latn \
    --joined-dictionary	\
    --srcdict ${home_dir}/NLLB-inference/dictionary.txt \
    --destdir ${data_dir}/data-bin-test/spa_Latn-${lang_dict[$l]}/ \
    --workers 10

done

cp ${data_dir}/data-bin-test/*/*.bin ${data_dir}/data-bin-test-combined
cp ${data_dir}/data-bin-test/*/*.idx ${data_dir}/data-bin-test-combined
cp ${data_dir}/data-bin-test/*/dict.*.txt ${data_dir}/data-bin-test-combined