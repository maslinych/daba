import readline
import sys
from daba.mparser import DictLoader, GrammarLoader, Processor
from pprint import pprint
# colours in terminal : https://stackoverflow.com/a/2616912
import re
import signal
#from Tkinter import Tk

def handler(signum, frame):
    print("use Shift+Ctrl+C to copy - just use (blank entry)/return to exit")
    #Tk().clipboard_get()   # copy anyway ?

signal.signal(signal.SIGINT, handler)

splitted=re.compile(r"́|̀|̌|̂|̧|̈")
mapping = { 'à':'à','á':'á', 'â':'â', 'é':'é', 'ê':'ê', 'è':'è', 'ë':'ë', 'ì':'ì', 'í':'í', 'î':'î', 'ï':'ï', 'ò':'ò', 'ó':'ó', 'ô':'ô', 'û':'û', 'ù':'ù', 'ú':'ú', 'ç':'ç'}
# tbc : more missing ? ...
  
def tomonolith(mystring) :
  if splitted.search(mystring) :
    for k, v in mapping.items():
      mystring = mystring.replace(k, v)
  return mystring

def mmlist(mrphx): # can handle multiple level mm
    mrphx=mrphx.replace("[","[ ")
    mrphx=mrphx.replace("]"," ]")
    mrphelem=mrphx.split(" ")
    mmprefix="\\mm"
    level=0
    mms=""
    for elem in mrphelem:
        if elem=="[":
            level+=1
            mmprefix=mmprefix+"m"
        elif elem=="]":
            level-=1
            mmprefix=mmprefix[:-1]
        else:
            if ":" in elem:
                mmlx,mmps,mmgloss=elem.split(":",2)
                mms+=mmprefix+" "+mmlx+":"+mmps+":"+tomonolith(mmgloss)+"\n"
            else:
                mms+=mmprefix+" "+elem   # ??? what happened ???
    return mms

#print('test mmlist: \n', mmlist('[mɔ̀ɔba:n:adulte [mɔ̀ɔ:n:homme ba:mrph:AUGM] kɔ̀dɔ:adj:vieux]'))
# to complement single level in glosslist from parser, 
#  load mmc glosses that exist in last build of the language dictionaries (export.sh):
#  bamadaba-mmc.txt, malidaba-mmc.txt or jula-mmc.txt
#   must be renamed as "mmc.txt" and placed in the current directory (where a gparser "run" subdir exists)
glossdict={}
has_mmc=False
try:
    mmcfile=open("mmc.txt",'r',encoding="utf-8")
    print("helper file mmc.txt found")
    has_mmc=True
except:
    print("no mmc helper file")
if has_mmc:
    mmcall=mmcfile.read()
    mmcfile.close()
    mmclist=mmcall.split("\n")
    for mmc in mmclist:
        lx,ps,glmm=mmc.split(":",2)
        if " " in glmm:
            gl,mm=glmm.split(" ",1)
            mmindex=lx+":"+ps+":"+gl
            glossdict[mmindex]=mm
    print("mmc available",len(glossdict))

def recursemm(y):
    mrph="["
    for z in y.morphemes:
        mpsfull=""
        for z1 in z.ps:
            mpsfull+=z1+"/"
        if mpsfull!="" : mpsfull=mpsfull[:-1]
        thismrph=z.form+":"+mpsfull+":"+tomonolith(z.gloss)
        if thismrph!="-:mrph:-" : 
            if has_mmc:
                if thismrph in glossdict:
                    thismrph=thismrph+" "+glossdict[thismrph]
            mrph+=thismrph+" "
        if z.morphemes: mrph+=recursemm(z)
    mrph+="] "
    return mrph


def glossprint(glosslist):
    for x in glosslist:
        #print("x:",x)
        mrph=""
        # checking for multilevel gloss: no found here    14/04/2024
        # fixed in formats1 30/09/2024
        # could simplify with mrph=str(glosslist) but I want the gloses in monolith
        # print("glossprint: x.morphemes=", x.morphemes)
        for y in x.morphemes : 
            mpsfull=""
            for y1 in y.ps:
                mpsfull+=y1+"/"
            if mpsfull!="" : mpsfull=mpsfull[:-1]
            thismrph=y.form+":"+mpsfull+":"+tomonolith(y.gloss)
            if thismrph!="-:mrph:-" : 
                if has_mmc:
                    if thismrph in glossdict:
                        thismrph=thismrph+" "+glossdict[thismrph]
                mrph+=thismrph+" "
            if y.morphemes: mrph+=recursemm(y)
            """
            if y.morphemes:
                mrph+="["
                for z in y.morphemes:
                    mpsfull=""
                    for z1 in z.ps:
                        mpsfull+=z1+"/"
                    if mpsfull!="" : mpsfull=mpsfull[:-1]
                    thismrph=z.form+":"+mpsfull+":"+tomonolith(z.gloss)
                    if thismrph!="-:mrph:-" : 
                        if has_mmc:
                            if thismrph in glossdict:
                                thismrph=thismrph+" "+glossdict[thismrph]
                        mrph+=thismrph+" "
                mrph+="] "
            """
        if mrph!="": 
            mrph=mrph.replace(' ]',']')
            mrph=mrph[:-1]
        mrphprint=""
        if mrph!="": mrphprint="["+mrph+"]"
        psfull=""
        for y in x.ps : psfull+=y+"/"
        if psfull!="": psfull=psfull[:-1]
        print(x.form+":"+psfull+":"+tomonolith(x.gloss), mrphprint)
        if mrph!="":
            print(mmlist(mrph))    
            # can only be single level : levels not returned in x.morphemes???  ;-(

def main():
    dl = DictLoader()
    gr = GrammarLoader()
    pp = Processor(dl, gr)
    while True:
        word = input('\033[42;30;1mEnter word:\033[0m ')
        if word=="" : sys.exit()
        stage,glosslist = pp.parser.lemmatize(word, debug=True)
        print('\033[1mFinal result:\033[0m')
        print(stage,glosslist)
        #  gloss=glosslist[0]
        #  print("\ngloss.ps",gloss.ps, len(gloss.ps))
        #  print("\ngloss.gloss",gloss.gloss)
        glossprint(glosslist)

        gloss=glosslist[0]
        if len(glosslist)==1:
            #if (len(gloss.ps)==0 and gloss.gloss=="") or (gloss.ps[0]=="n.prop" and (gloss.gloss=="NOM" or gloss.gloss=="TOP")):
            glossps=""
            if len(gloss.ps)>0 : glossps=gloss.ps[0]
            if (len(gloss.ps)==0 and gloss.gloss=="") or (glossps=="n.prop"):
                if word[0].isupper():
                    #word=word[0].lower()+word[1:]
                    word=word.lower()
                    stage2,glosslist2 = pp.parser.lemmatize(word)
                    print('\033[1mAlternative result lowercase:\033[0m')
                    #print(stage,glosslist)
                    glossprint(glosslist2)
                else:
                    #word=word[0].upper()+word[1:]
                    word=word.capitalize()
                    stage2,glosslist2 = pp.parser.lemmatize(word)
                    print('\033[1mAlternative result uppercase:\033[0m')
                    #print(stage,glosslist)
                    glossprint(glosslist2)

                print ("\033[1mpotential global result\033[0m")  # (from mparser - modified - check differences)
                if len(glosslist2)>1 :
                  #or not ((len(glosslist2.ps)==0 and glosslist2.gloss=="")
                  #or (len(glosslist2.ps)==1 and glosslist2.ps[0]=="n.prop" and glosslist2.gloss=="NOM")):
                    if (len(gloss.ps)==0 and gloss.gloss=="") or (len(gloss.ps)==1 and gloss.ps[0]=="n.prop" and gloss.gloss=="NOM") :
                        glosslist=glosslist2
                    else:
                        glosslist=glosslist+glosslist2    
                glossprint(glosslist)


if __name__ == '__main__':
    main()
