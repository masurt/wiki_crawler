import zlib
from bs4 import BeautifulSoup
from bs4.element import Comment
import urllib.request
from typing import Set, Union, Optional, List

import networkx as nx
import pandas as pd


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
    def __init__(self, base_url, depth=0, language="English"):
        self.base_page = WikiPage(base_url, language)
        self.depth = depth
        self.language = language

        self.link_graph: Union[nx.DiGraph, None] = None
        self.build_link_graph()

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

        df_rel = df.div(df[self.language], axis="index")
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
            top_page = WikiPage(top_link, self.language)
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

    def set_depth(self, depth):
        self.depth = depth
        self.build_link_graph()

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

        page = WikiPage(page_link, self.language)
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


class WikiPage:
    start_of_url_string = "https://"
    end_of_root_url_string = ".wikipedia.org"

    def __init__(self, url):
        self.url: str = url
        self.validate_url()

        self._soup = None

        self.language_article_lengths_dataframe: Optional[pd.DataFrame] = None
        self.other_language_pages: List[WikiPage] = []

    def validate_url(self):
        error_messages = ""
        if not self.url.startswith(self.start_of_url_string):
            error_messages += f"Malformatted url: make sure it starts with {self.start_of_url_string}\n"
        if not self.end_of_root_url_string in self.url:
            error_messages += f"Malformatted url: make sure it contains {self.end_of_root_url_string}\n"

        if error_messages != "":
            raise ValueError(
                f"Malformatted url: make sure it starts with {self.start_of_url_string}"
            )

    @property
    def soup(self):
        if self._soup:
            return self._soup
        self._soup = self.get_soup()
        return self._soup

    def get_soup(self):
        html = urllib.request.urlopen(self.url).read()
        return BeautifulSoup(html, "html.parser")

    @property
    def article_content(self):
        content = self.soup.find("div", {"id": "content"})
        if not content:
            content = self.soup.find("main", {"id": "content"})
        return content

    @property
    def root_url(self):
        end_of_root_index = self.url.find(self.end_of_root_url_string)
        if end_of_root_index != -1:
            root_url = self.url[: end_of_root_index + len(self.end_of_root_url_string)]
            return root_url
        else:
            raise Exception(f"Root url of url {self.url} could not be determined.")

    @property
    def language_code(self):
        index_pre_language_code_string = self.root_url.find(self.start_of_url_string)
        language_code = self.root_url[
            index_pre_language_code_string
            + len(self.start_of_url_string) : -len(self.end_of_root_url_string)
        ]
        return language_code

    @staticmethod
    def get_language_code_from_url(url):
        pre_language_code_string = "//"
        post_language_code_string = "."

        index_pre_language_code_string = url.find(pre_language_code_string)
        url_starting_with_language_code = url[
            index_pre_language_code_string + len(pre_language_code_string) :
        ]

        index_post_language_code_string = url_starting_with_language_code.find(
            post_language_code_string
        )
        language_code = url_starting_with_language_code[
            :index_post_language_code_string
        ]

        return language_code

    def build_language_article_lengths_dataframe(
        self, only_use_these_languages: [str] = None, compressed_length=True
    ):
        language_urls: [str] = self.get_other_language_urls()
        if only_use_these_languages:
            language_urls = list(
                filter(
                    lambda url: self.get_language_code_from_url(url)
                    in only_use_these_languages,
                    language_urls,
                )
            )

        language_pages = []
        for language_url in language_urls:
            for already_loaded_page in self.other_language_pages:
                if already_loaded_page.url == language_url:
                    language_pages.append(already_loaded_page)
                    break
            else:  # no break -> language page not found in already loaded other language pages
                page = WikiPage(language_url)
                language_pages.append(page)
                self.other_language_pages.append(page)

        language_pages.append(self)

        language_article_lengths_df = pd.DataFrame()
        for page in language_pages:
            language_code = page.language_code

            if compressed_length:
                language_article_lengths_df.loc[
                    self.url, language_code
                ] = page.get_article_compressed_length()
            else:
                language_article_lengths_df.loc[
                    self.url, language_code
                ] = page.get_article_length()

        self.language_article_lengths_dataframe = language_article_lengths_df
        return language_article_lengths_df

    def get_language_article_lengths_dataframe(self):
        if self.language_article_lengths_dataframe is not None:
            return self.language_article_lengths_dataframe
        else:
            raise Exception(
                "language_article_lengths_dataframe needs to be build first."
            )

    def get_article_length(self):
        text = self.get_article_visible_text()
        return len(text)

    def get_article_compressed_length(self):
        text = self.get_article_visible_text()
        compressed_text = zlib.compress(text.encode("utf-8"))
        return len(compressed_text)

    def get_article_visible_text(self):
        texts = self.article_content.findAll(text=True)
        visible_texts = filter(tag_visible, texts)
        text = " ".join(t.strip() for t in visible_texts)
        return text

    def get_other_language_urls(self) -> [str]:
        language_lis = self.soup.find("nav", {"id": "p-lang"}).find_all("li")
        links = []
        for li in language_lis:
            a = li.find("a")
            links.append(a.get("href"))
        return links

    def get_all_article_to_article_links(self):
        """Filters out things links to things other than wikipedia articles and links to "identifiers" (like doi, isbn) which occur often."""
        all_article_links = self.get_all_article_links()
        article_to_article_links = []
        for link in all_article_links:
            if (
                link.startswith("/wiki/")
                and not link.endswith("(identifier)")
                and not link.startswith("/wiki/Category")
                and not link.startswith("/wiki/Wikipedia")
                and not link.startswith("/wiki/Help")
                and not link.startswith("/wiki/File")
                and not link.startswith("/wiki/Wayback_Machine")
                and not link.startswith("/wiki/Template")
            ):
                article_to_article_links.append(link)

        article_to_article_links = [
            self.remove_url_fragment(a2a_link) for a2a_link in article_to_article_links
        ]
        return [self.root_url + link for link in article_to_article_links]

    def get_all_article_links(self):
        """Get all links in article body."""
        article_links = self.get_all_links_from_soup(self.article_content)
        # filter out None links
        article_links = list(filter(lambda link: link is not None, article_links))
        return article_links

    def get_all_links(self):
        return self.get_all_links_from_soup(self.soup)

    @staticmethod
    def get_all_links_from_soup(soup):
        links = []
        for link in soup.find_all("a"):
            links.append(link.get("href"))
        return links

    def remove_url_fragment(self, url: str):
        hash_index = url.rfind("#")
        if hash_index != -1:
            return url[:hash_index]
        return url

    def print_pretty_soup(self):
        print(self.soup.prettify())

    def get_page_info(self):
        info = ""
        info += f"Page url: {self.url}\n"
        info += f"Root url: {self.root_url}\n"
        info += f"Language code: {self.language_code}\n"
        info += f"Article length (compressed): {self.get_article_length()} ({self.get_article_compressed_length()})\n"
        info += f"Language lengths dataframe build: {self.language_article_lengths_dataframe is not None}\n"
        info += f"# of article to article links: {len(self.get_all_article_to_article_links())}\n"
        info += f"# languages available: {len(self.get_other_language_urls()) + 1}"
        return info

    def __repr__(self):
        repr = f"RootWikiPage Object:\n__dict__: {self.__dict__}"
        return repr

    def __str__(self):
        repr = f"RootWikiPage Object: url: {self.url}"
        return repr

    def __eq__(self, other):
        return self.url == other.url
