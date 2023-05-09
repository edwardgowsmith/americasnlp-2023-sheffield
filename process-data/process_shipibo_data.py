import csv

with open("americasnlp2021-st/data/shipibo_konibo-spanish/extra/traduccionTsanas1.csv", encoding='latin-1') as f:
    with open("americasnlp2021-st/data/shipibo_konibo-spanish/extra/traduccionTsanas1.shi", "w") as outf1:
        with open("americasnlp2021-st/data/shipibo_konibo-spanish/extra/traduccionTsanas1.es", "w") as outf2:
            reader = csv.reader(f, quotechar='"')
            for row in reader:
                outf1.write(row[2])
                outf1.write("\n")
                outf2.write(row[3])
                outf2.write("\n")
