import os.path
from io import StringIO

import requests

import pandas as pd
np = pd.np


path = lambda filename, sep='/': os.path.join(*filename.split(sep))

ENDPOINT_URL = 'http://localhost:7200/repositories/recommender'

namespaces = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "v": "http://www.w3.org/2006/vcard/ns#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "dct": "http://purl.org/dc/terms/",
    "ont": "http://schema.org/ontology/",
    "": "http://schema.org/resource/"
}

def run_query(query, *args, use_prefixes=True):
    r = requests.post(ENDPOINT_URL, data={'query': query % args})

    s = StringIO()
    s.write(r.text)
    s.seek(0)

    df = pd.read_csv(s)

    if use_prefixes:
        def replace_namespaces(x):
            for prefix, url in namespaces.items():
                if type(x) == str and x.startswith(url):
                    return x.replace(url, prefix + ':')
            else:
                return x

        
        for col in df:
            if df[col].dtype in (np.object, str):
                df[col] = df[col].apply(replace_namespaces)
        
    return df


class Menu:

    variables = {}

    def __init__(self, name, options):
        """
            options is a list with tuples of three elements:
                - option name
                - option description
                - option function
        """

        self.name = name
        self.options = options


    def run(self): return self()

    def __call__(self):
        while True:
            try:
                print('-' * 20)
                if self.name is not None:
                    print(self.name)
                    print('-' * 20)
                
                print()

                print('Type an option number or [q]uit')

                for n, (name, desc, _) in enumerate(self.options):
                    print('%d. %s' % (n + 1, name))
                    if desc is not None:
                        print('\t%s' % desc)

                print()
                opt = input('> ').lower().strip()
                if opt in ('q', 'quit'): # quit
                    break

                elif opt.isdigit():
                    opt = int(opt)

                    if opt < 1 or opt > len(self.options):
                        raise ValueError(
                            'Input must be one of the option numbers or q'
                        )

                    func = self.options[opt - 1][2]
                    res = func()
                    
                    if res is not None:
                        return res

                else:
                    raise ValueError(
                        'Input must be one of the option numbers or q'
                    )

            except KeyboardInterrupt:
                raise

            except Exception as e:
                print('Error: %s' % e)