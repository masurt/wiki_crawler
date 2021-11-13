from bs4.element import Comment
from typing import Set, Union, Optional

import networkx as nx
import pandas as pd

import sys

print(sys.path)
from .wiki_page import WikiPage


def tag_visible(element):
    if element.parent.name in [
        "style",
        "script",
        "head",
        "title",
        "meta",
        "[document]",
    ]:
        return False
    if isinstance(element, Comment):
        return False
    return True


class WikiGraph:
    def __init__(self, base_url):
        self.base_page = WikiPage(base_url)
        self.language_code = self.base_page.language_code

        self.graph: Optional[nx.DiGraph] = None

        self.graph_links_language_article_lengths_dict: Union[dict, None] = None

    def check_graph_is_built(self):
        if self.graph is None:
            raise Exception(
                "Link graph not build. "
                "First build it to the required depth with WikiGraph.build_link_graph()"
            )

    def build_graph(self, depth):
        page_graph = nx.DiGraph()
        page_graph.add_node(self.base_page)

        page_graph = self.add_page_to_graph_to_depth(
            page_graph, self.base_page, depth=depth
        )
        self.graph = page_graph
        return self.graph

    def add_page_to_graph_to_depth(
        self,
        graph: nx.DiGraph,
        page: WikiPage,
        depth: int,
        searched_urls: Set = None,
    ) -> nx.DiGraph:

        if depth == 0:
            return graph

        if not searched_urls:
            searched_urls = set()

        for link in page.get_all_article_to_article_links():
            if link in searched_urls:
                continue
            new_page = WikiPage(link)
            graph.add_edge(page, new_page)
            graph = self.add_page_to_graph_to_depth(
                graph, new_page, depth=depth - 1, searched_urls=searched_urls
            )
        searched_urls.add(page.url)

        return graph
