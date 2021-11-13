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

        self.link_graph: Optional[nx.DiGraph] = None
        self.page_graph: Optional[nx.DiGraph] = None
        # self.build_link_graph()
        # self.build_graph()

        self.graph_links_language_article_lengths_dict: Union[dict, None] = None

    def check_link_graph_is_built(self):
        if self.link_graph is None:
            raise Exception(
                "Link graph not build. "
                "First build it to the required depth with WikiGraph.build_link_graph()"
            )

    def analyse_language_completeness(
        self, only_use_languages=None, top_n_links=None, compressed_length=True
    ):
        self.check_link_graph_is_built()

        graph_links_language_article_lengths_dict = (
            self.get_graph_links_language_article_lengths_dict(
                top_n_links=top_n_links,
                compressed_length=compressed_length,
                only_use_languages=only_use_languages,
            )
        )

        df: pd.DataFrame = graph_links_language_article_lengths_dict[
            "lengths_dataframe"
        ]

        missing_languages = {
            link: list(df.loc[link][df.loc[link].isna()].index) for link in df.index
        }

        df_rel = df.div(df[self.language_code], axis="index")
        print(df_rel)
        short_languages = {
            link: list(df_rel.loc[link][df_rel.loc[link] < 0.5].index)
            for link in df_rel.index
        }
        return missing_languages, short_languages

    def get_graph_links_language_article_lengths_dict(
        self, top_n_links=None, compressed_length=True, only_use_languages=None
    ):
        self.check_link_graph_is_built()
        if self.graph_links_language_article_lengths_dict is not None:
            return self.graph_links_language_article_lengths_dict

        in_degrees = list(self.link_graph.in_degree)
        links_sorted_by_in_degree = [
            (val, link)
            for link, val in sorted(in_degrees, key=lambda deg: deg[1], reverse=True)
        ]
        if top_n_links:
            top_links = links_sorted_by_in_degree[
                : min(top_n_links, len(links_sorted_by_in_degree))
            ]
        else:
            top_links = links_sorted_by_in_degree

        graph_links_language_article_lengths = pd.DataFrame()

        for _, top_link in top_links:
            top_page = WikiPage(top_link)
            language_article_lengths = (
                top_page.build_language_article_lengths_dataframe(
                    only_use_these_languages=only_use_languages,
                    compressed_length=compressed_length,
                )
            )
            graph_links_language_article_lengths = (
                graph_links_language_article_lengths.append(language_article_lengths)
            )

        self.language_article_lengths_dict = {
            "lengths_dataframe": graph_links_language_article_lengths,
            "compressed": compressed_length,
            "languages": list(graph_links_language_article_lengths.columns),
        }
        return self.language_article_lengths_dict

    def build_graph(self, depth):
        page_graph = nx.DiGraph()
        page_graph.add_node(self.base_page)

        page_graph = self.add_page_to_graph_to_depth(
            page_graph, self.base_page, depth=depth
        )
        self.page_graph = page_graph
        return self.page_graph

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

    def build_link_graph(self) -> None:
        link_graph = nx.DiGraph()
        link_graph.add_node(self.base_page.url)

        link_graph = self.add_page_to_link_graph_to_depth(
            link_graph, self.base_page.url, depth=self.depth
        )
        self.link_graph = link_graph

    def add_page_to_link_graph_to_depth(
        self,
        link_graph: nx.DiGraph,
        page_link: [str],
        depth: int,
        searched_links: Set = None,
    ) -> nx.DiGraph:
        if depth == 0:
            return link_graph

        if not searched_links:
            searched_links = set()

        page = WikiPage(page_link)
        sublinks = page.get_all_article_to_article_links()

        for ilink, link in enumerate(sublinks):
            if link in searched_links:
                # print(f"Skipping link {link}.")
                continue
            if depth > 1:
                print(
                    f"Adding sublink {ilink}/{len(sublinks)}, depth {depth}, edge {(page_link[24:], link[24:])}"
                )
            link_graph.add_edge(page_link, link)
            link_graph = self.add_page_to_link_graph_to_depth(
                link_graph, link, depth=depth - 1, searched_links=searched_links
            )
        searched_links.add(page_link)

        return link_graph
