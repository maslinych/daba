import readline
import sys
from daba.mparser import DictLoader, GrammarLoader, Processor
from pprint import pprint

def main():
    dl = DictLoader()
    gr = GrammarLoader()
    pp = Processor(dl, gr)
    while True:
        word = input('Enter word:')
        result = pp.parser.lemmatize(word, debug=True)
        print('Final result::')
        pprint(result)

if __name__ == '__main__':
    main()
