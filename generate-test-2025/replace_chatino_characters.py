replacements = {'A': "ᴬ", 'H': "ᴴ", "J":'ᴶ', "E":"ᴱ", "I":"ᴵ", "c":"ᶜ", "K": "ᴷ", "B":"ᴮ", "G":"ᴳ", "f":"ᶠ"}

with open("test-translation/ctp.hyp") as inf:
    with open("test-translation/ctp_adj.hyp", "w") as outf:
        for line in inf:
            outline = ''
            for x in line.split():
                y = ''
                if x[-1] in replacements.keys():
                    y = x[:-1] + replacements[x[-1]]
                else:
                    y = x 
                outline += y + ' '
            outf.write(outline)
            outf.write("\n")