#! /usr/bin/env python

import argparse
import asyncio
from pyppeteer import launch
from datetime import datetime
from pathlib import Path


sizes = {"small": [1024, 768], "medium": [1280, 1024], "large": [1600, 1200]}


def fixup(s, x):
    if s in x:
        if x.split(s)[0] != "":
            return x.split(s)[0]
        else:
            return x.split(s)[1]
    else:
        return x


def fixup_strs(strs, x):
    for s in strs:
        x = fixup(s, x)
    return x


def url2filename(url):
    x = url.rstrip().rstrip("/").split("/")[-1:][0]
    return fixup_strs(["%3F", "?", "#"], x)


class Project:
    def __init__(self, rootdir=None):
        if not rootdir:
            now = datetime.now()
            rootdir = now.strftime("%Y-%m-%d-%H-%M-%S")
        self.rootdir = Path(rootdir)
        self.setup_dirs()

    def setup_dirs(self):
        for d in ["images", "headers", "html"]:
            subdir = self.rootdir / d
            subdir.mkdir(parents=True, exist_ok=True)

    def _write(self, url, data, subdir, extension, mode):
        filename = f"{url2filename(url)}.{extension}"
        path = self.rootdir / subdir / filename

        with open(path, mode) as f:
            f.write(data)

    def write_headers(self, url, headers):
        data = "".join([f"{k} : {v}\n" for k, v in headers.items()])
        self._write(url, data, "headers", "header.txt", "w")

    def write_body(self, url, data):
        self._write(url, data, "html", "html", "w")

    def write_screenshot(self, url, data):
        self._write(url, data, "images", "png", "wb")


async def get_url(browser, url, viewport_width, viewport_height):
    # open a new page, I still dont know how to control the default page opened
    page = await browser.newPage()

    # set resolution of browser view port
    await page.setViewport({"width": viewport_width, "height": viewport_height})

    # go to url and wait for page to load
    try:
        page_response = await page.goto(url, {"waitUntil": "networkidle2"})

        if page_response:
            args.project.write_headers(url, page_response.headers)
        else:
            return

        body = await page_response.text()
        args.project.write_body(url, body)

        screenshot = await page.screenshot()
        args.project.write_screenshot(url, screenshot)
        await page.close()

    except Exception as exc:
        print(f"{url} could not be resolved or accessed. {repr(exc)}")


async def safe_get_url(tabs, browser, url, viewport_width, viewport_height):
    async with tabs:  # semaphore limits num of simultaneous downloads
        return await get_url(browser, url, viewport_width, viewport_height)


async def browse_urls(
    threads, urls, width, height, show_browser, ignore_ssl_errors
):
    tabs = asyncio.Semaphore(
        threads
    )  # semaphore limits num of simultaneous tabs
    # Launch a browser either visible or not, and ignore errors or not
    browser = await launch(
        {"headless": not (show_browser), "ignoreHTTPSErrors": ignore_ssl_errors}
    )
    tasks = [
        asyncio.ensure_future(
            safe_get_url(tabs, browser, url, width, height)
        )  # creating task starts coroutine
        for url in urls
    ]
    await asyncio.gather(*tasks)  # await moment all downloads done


parser = argparse.ArgumentParser(prog="Screen Profiler")
parser.add_argument(
    "URLfile", type=str, help="File with list of urls, one per line"
)
parser.add_argument(
    "-p",
    "--project-name",
    dest="project_name",
    action="store",
    type=str,
    default="",
    help="Project name will be created as directory to store data",
)
parser.add_argument(
    "-t",
    "--tabs",
    dest="tabs",
    action="store",
    type=int,
    default=10,
    help="The number of tabs you want the web browser to open.",
)
parser.add_argument(
    "-s",
    "--size",
    dest="size",
    action="store",
    nargs=2,
    default=[1280, 1024],
    help="Screenshot size (width height). Defaults to [1280, 1024]",
)
parser.add_argument(
    "-v",
    "--verbose",
    dest="verbose",
    action="store_true",
    help="Render verbose output, including redirects and program errors.",
)
parser.add_argument(
    "-i",
    "--ignore-tls-errors",
    dest="ignore_tls",
    action="store_true",
    help="Don't verify SSL/TLS certificates.",
)
parser.add_argument(
    "-b",
    "--browser",
    dest="browser",
    action="store_true",
    help="Show browser while operations are ongoing.",
)

args = parser.parse_args()
args.project = Project(args.project_name)  # also inits directories

width, height = int(args.size[0]), int(args.size[1])

with open(args.URLfile) as f:
    urls = f.readlines()

asyncio.get_event_loop().run_until_complete(
    browse_urls(
        threads=args.tabs,
        urls=urls,
        width=width,
        height=height,
        show_browser=args.browser,
        ignore_ssl_errors=args.ignore_tls,
    )
)
