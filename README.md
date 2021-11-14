# Wiki Crawler

lets you analyse a wiki article, linked articles and lengths of their versions in other languages. 
You start with one article and it follows all links in the article and builds a graph (implemented with the networkx packge).
You can then generate a pandas `DataFrame` with all found articles and their lengths in other languages.

_Warning_: The live Wikipedia is queried and the requests are rate limited at 1/second, which is what they ask for in [https://en.wikipedia.org/wiki/Wikipedia:Database_download#Why_not_just_retrieve_data_from_wikipedia.org_at_runtime?](https://en.wikipedia.org/wiki/Wikipedia:Database_download#Why_not_just_retrieve_data_from_wikipedia.org_at_runtime?). This is rather slow. Change at your own risk. 
Don't blame me if your IP gets blocked.  

By default the article text is compressed with
```zlib.compress(text.encode("utf-8"))```
before taking its length to reduce inherent differences in lengths of languages.

Try the [examples.ipynb](examples.ipynb) for basic analysis examples

## Setup

Install python packages in virtual environment
```
python3 -m venv wiki_crawler_env
source ./wiki_crawler_env/bin/activate
pip install -r requirements.txt
```

Install virtual environment as jupyter kernel
```
python -m ipykernel install --user --name=wiki_crawler_env
```

Start jupyter notebook from top project level with 
```
jupyter notebook
```
