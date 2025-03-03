# Sheffield's Submission to AmericasNLP 2023
This repository contains the code to reproduce The University of Sheffield's Submission to the AmericasNLP 2023 Shared Task on Machine Translation into Indigenous Languages, which is also used as a baseline for the 2024 and 2025 editions of the AmericasNLP Shared Task. 

Please see our paper for further details: [Sheffield's Submission to the AmericasNLP Shared Task on Machine Translation into Indigenous Languages.](https://aclanthology.org/2023.americasnlp-1.21/)

We also provide links to download our best-performing models (excluding ensembles) at https://drive.google.com/drive/folders/12MCYFD5Q9YRWrRCWjqjEorsDLgGp_gXB?usp=sharing.

## Training

In order to train our models, first install our modified version of fairseq

```console
cd fairseq
pip install --editable .
```

This version of fairseq extends the embeddings of NLLB to cover the additional language tags, and reports ChrF++ at every valid interval. 

Then, process_data.sh can be used to download and process all of the training and evaluation data. 

train-models-2023/ contains scripts for running our experiments for our submission to the 2023 shared task. Submission 3 is trained using the script: train-nllb-1.3B-unfreeze-everything-all-pairs-seed-1-sampling-3-detok-train1M.sh

## Citation

If you use our models in your work, please cite:

```bibtex
@inproceedings{gow-smith-snchez-villegas-2023-sheffields,
    title = "{S}heffield`s Submission to the {A}mericas{NLP} Shared Task on Machine Translation into Indigenous Languages",
    author = "Gow-Smith, Edward  and
      S{\'a}nchez Villegas, Danae",
    editor = "Mager, Manuel  and
      Ebrahimi, Abteen  and
      Oncevay, Arturo  and
      Rice, Enora  and
      Rijhwani, Shruti  and
      Palmer, Alexis  and
      Kann, Katharina",
    booktitle = "Proceedings of the Workshop on Natural Language Processing for Indigenous Languages of the Americas (AmericasNLP)",
    month = jul,
    year = "2023",
    address = "Toronto, Canada",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2023.americasnlp-1.21/",
    doi = "10.18653/v1/2023.americasnlp-1.21",
    pages = "192--199"
}
```
