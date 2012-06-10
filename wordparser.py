import readline
import sys
from mparser import DictLoader, GrammarLoader, Processor
from pprint import pprint

def main():
    dl = DictLoader()
    gr = GrammarLoader()
    pp = Processor(dl, gr, script="new")
    while True:
        word = raw_input('Enter word:').decode(sys.stdin.encoding)
        result = pp.parser.lemmatize(word, debug=True)
        print 'Final result::'
        pprint(result)

if __name__ == '__main__':
    main()
