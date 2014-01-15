#!//usr/bin/env python

import itertools
import logging
import os
import shutil
import sys
import urllib2
import yaml
import gzip
import StringIO

# some constants to download the articles list we need to scrap
URL_LIST = (
    "http://dumps.wikimedia.org/%(language)swiki/latest/"
    "%(language)swiki-latest-all-titles-in-ns0.gz"
)
ART_INCLUDE = "utilities/include.txt"
ART_ALL = "all_articles.txt"

# the directory (inside the one specified by the user) that actually
# holds the articles and images
DUMP_ARTICLES = "articles"
DUMP_IMAGES = "images"

# base url
WIKI_BASE = 'http://%(language)s.wikipedia.org'


# set up logging
logger = logging.getLogger()
handler = logging.StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter(
    "%(asctime)s  %(name)-15s %(levelname)-8s %(message)s")
handler.setFormatter(formatter)
logger.setLevel(logging.DEBUG)
logger = logging.getLogger("cdpetron")


def get_lists(branch_dir, language, config):
    """Get the list of wikipedia articles."""
    fh_artall = open(ART_ALL, "wb")

    url = URL_LIST % dict(language=language)
    logger.info("Getting list file: %r", url)
    u = urllib2.urlopen(url)
    logger.debug("Got headers: %s", u.headers.items())
    fh = StringIO.StringIO(u.read())
    gz = gzip.GzipFile(fileobj=fh)

    # walk through lines, easier to count and assure all lines are proper
    # saved into final file, mainly because of last line separator
    q = 0
    for line in gz:
        fh_artall.write(line + "\n")
        q += 1
    tot = q
    gz.close()
    logger.info("Downloaded %d general articles", q)

    logger.info("Getting the articles from namespaces")
    q = 0
    for article in list_articles_by_namespaces.get_articles(language):
        q += 1
        fh_artall.write(article.encode('utf8') + "\n")
    tot += q
    logger.info("Got %d namespace articles", q)

    q = 0
    for page in config['include']:
        q += 1
        fh_artall.write(page.encode('utf8') + "\n")
    tot += q
    logger.info("Have %d articles to mandatorily include", q)

    fh_artall.close()
    logger.info("Total of articles: %d", tot)


def scrap(branch_dir, dump_dir):
    """Get the pages from wikipedia."""
    logger.info("Let's scrap")
    assert os.getcwd() == dump_dir
    res = os.system("python %s/utilities/scraper.py %s %s" % (
        branch_dir, ART_ALL, DUMP_ARTICLES))
    if res != 0:
        logger.warning("Bad result code from scrapping: %r", res)

    logger.info("Checking scraped size")
    articles_dir = os.path.join(dump_dir, DUMP_ARTICLES)
    total = os.stat(articles_dir).st_size
    for dirpath, dirnames, filenames in os.walk(articles_dir):
        for name in itertools.chain(dirnames, filenames):
            size = os.stat(os.path.join(dirpath, name)).st_size

            # consider that the file occupies whole 512 blocks
            blocks, tail = divmod(size, 512)
            if tail:
                blocks += 1
            total += blocks * 512
    logger.info("Total size of scraped articles: %d MB", total // 1024 ** 2)


def clean(branch_dir, dump_dir):
    """Clean and setup the temp directory."""
    # we need a directory for the images in the dump dir (but keep it
    # if already there, we want to cache images!)
    image_dump_dir = os.path.join(dump_dir, DUMP_IMAGES)
    logger.info("Assure directory for images is there: %r", image_dump_dir)
    if not os.path.exists(image_dump_dir):
        os.mkdir(image_dump_dir)

    # let's create a temp directory for the generation with a symlink to
    # images (clean it first if already there). Note thtat 'temp' and
    # 'images' are hardcoded here, as this is what expects
    # the generation part)
    temp_dir = os.path.join(branch_dir, "temp")
    if os.path.exists(temp_dir):
        logger.info("Recursive deletion of old temp dir: %r", temp_dir)
        shutil.rmtree(temp_dir)

    logger.info("Temp dir setup: %r", temp_dir)
    os.mkdir(temp_dir)
    os.symlink(image_dump_dir, os.path.join(temp_dir, "images"))


def main(branch_dir, dump_dir, language, config, nolists, noscrap, noclean):
    """Main entry point."""
    logger.info("Branch directory: %r", branch_dir)
    logger.info("Dump directory: %r", dump_dir)
    logger.info("Generating for language: %r", language)
    logger.info("Language config: %r", config)
    logger.info("Options: nolists=%s noscrap=%s noclean=%s",
                nolists, noscrap, noclean)
    os.chdir(dump_dir)

    if not nolists:
        get_lists(branch_dir, language, config)

    if not noscrap:
        scrap(branch_dir, dump_dir)

    if not noclean:
        clean(branch_dir, dump_dir)

    os.chdir(branch_dir)
    generar.main(dump_dir, 'cd')


if __name__ == "__main__":
    nolists = noscrap = noclean = False
    if "--no-lists" in sys.argv:
        sys.argv.remove("--no-lists")
        nolists = True
    if "--no-scrap" in sys.argv:
        sys.argv.remove("--no-scrap")
        noscrap = True
    if "--no-clean" in sys.argv:
        sys.argv.remove("--no-clean")
        noclean = True

    if len(sys.argv) != 5:
        print ("Usage: %s [--no-lists] [--no-scrap] [--no-clean] "
               "<branch_dir> <dump_dir> <language> <configfile>" % sys.argv[0])
        exit()

    branch_dir = os.path.abspath(sys.argv[1])
    dump_dir = os.path.abspath(sys.argv[2])
    language = sys.argv[3]
    with open(sys.argv[4]) as fh:
        config = yaml.load(fh)[language]

    # branch dir must exist
    if not os.path.exists(branch_dir):
        print "The branch dir doesn't exist!"
        exit()

    # fix sys path to branch dir and import the rest of stuff from there
    sys.path.insert(1, branch_dir)
    utils_dir = os.path.join(branch_dir, "utilities")
    sys.path.insert(1, utils_dir)
    import list_articles_by_namespaces, generar

    # dump dir may not exist, let's just create if it doesn't
    if not os.path.exists(dump_dir):
        os.mkdir(dump_dir)

    main(branch_dir, dump_dir, language, config,
         nolists=nolists, noscrap=noscrap, noclean=noclean)
