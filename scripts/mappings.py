#!/usr/bin/env python3
# Author: Álvaro Parafita (parafita.alvaro@gmail.com)

import argparse

import re
import json
import gzip
import os.path

from copy import deepcopy

from rdflib import Graph
from rdflib.term import URIRef, Literal
import rdflib.term
import rdflib.namespace
from rdflib.namespace import RDF, RDFS, FOAF

from rdflib.plugin import register, Parser
register('json-ld', Parser, 'rdflib_jsonld.parser', 'JsonLDParser')


class Mapper:

    @staticmethod
    def map(mapping, graph_format='n3'):
        mapper = mapping.pop('mapper')
        input_filename = mapping.pop('filename')
        output_filename = mapping.pop('output')

        try:
            graph = getattr(Mapper, mapper)(input_filename, **mapping)
        except AttributeError:
            raise KeyError(mapper)

        graph.serialize(
            output_filename, format=graph_format
        )


    @staticmethod
    def rdflib(filename, format):
        return Graph().parse(filename, format=format)

    @staticmethod
    def json(filename, context=None):
        data = read_json(filename)

        if context:
            context = read_json(context)

            for d in data:
                d.update(context)

        return Graph().parse(data=json.dumps(data), format='json-ld')

    @staticmethod
    def sparql(filename, mapping, format):
        mapping = read_json(mapping)
        namespaces = mapping.get('namespaces', {})

        graph = Graph()

        for prefix, url in namespaces.items():
            graph.bind(prefix, url)

        query_graph = Graph().parse(filename, format=format)
        res = query_graph.query(mapping['query'], initNs=namespaces)

        variables = list(map(str, res.vars))
        res = list(map(lambda l: dict(zip(variables, l)), res))

        context = mapping['context']
        id_vars = re.findall(r'\{(.*?)\}', context['@id'])

        # prefix replacement
        for k, v in context.items():
            for prefix, url in namespaces.items():
                if v.startswith(prefix + ':'):
                    context[k] = v.replace(prefix + ':', url, 1)
                    break # go on with the next property

        # Add the triplets to the graph
        for row in res:
            row_context = {
                k: URIRef(v.format(**{ v: row[v] for v in id_vars }))

                for k, v in context.items()
            }

            subject = row_context['@id']
            graph.add((subject, RDF.type, row_context['@type']))

            variables = {
                k[1:]: v

                for k, v in row_context.items()
                if k.startswith('?')
            }

            for var_name, predicate in variables.items():
                graph.add(
                    (subject, predicate, Literal(row[var_name]))
                )

        return graph


def read_json(filename):
    """ Reads and parses json files, accepting gzip-compressed jsons """
    if filename.endswith('.gz'):
        open_func = gzip.open
    else:
        open_func = open
        
    with open_func(filename, 'rt') as f:
        return json.load(f)


def main(args):
    graph_format = args.graph_format

    for config in args.config:
        config = read_json(config)
        
        for mapping in config:
            Mapper.map(mapping, graph_format)


if __name__ == '__main__': 
    parser = argparse.ArgumentParser(
        description='Map sources to a single graph'
    )

    parser.add_argument(
        'config', help='configuration filenames', 
        type=str, nargs='+'
    )
    parser.add_argument(
        '-f', '--format', dest='graph_format', 
        help='output graph format: xml, n3, turtle, nt, pretty-xml, ' +
             'trix, trig or nquads',
        default='turtle'
    )

    args = parser.parse_args()

    main(args)