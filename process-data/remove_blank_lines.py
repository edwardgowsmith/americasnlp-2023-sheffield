import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--path1', type=str)
parser.add_argument('--path2', type=str)

args = parser.parse_args()

with open(args.path1) as f1:
    lines_1 = f1.readlines()
    with open(args.path2) as f2:
        lines_2 = f2.readlines()

        with open(args.path1+'_filtered', "w") as outf1:
            with open(args.path2+'_filtered', "w") as outf2:
                    for x, y in zip(lines_1, lines_2):
                        if x.strip() == '' or y.strip() == '':
                            continue
                        outf1.write(x)
                        outf2.write(y)
