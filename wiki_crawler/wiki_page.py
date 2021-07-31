import zlib
from bs4 import BeautifulSoup
from bs4.element import Comment
import urllib.request
from typing import Optional, List

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
                and not link.startswith("/wiki/Portal")
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
        repr = f"WikiPage {self.url}"
        return repr

    def __str__(self):
        repr = f"RootWikiPage Object: url: {self.url}"
        return repr

    def __eq__(self, other):
        if type(other) == WikiPage:
            return self.url == other.url
        if type(other) == str:
            return self.url == other

    def __hash__(self):
        return hash(self.url)
