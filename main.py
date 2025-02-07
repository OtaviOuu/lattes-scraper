from scrapy.crawler import CrawlerProcess
from scrapy import Spider
from scrapy.http import Request, Response

from playwright.async_api import Page
from scrapy_playwright.page import PageMethod

from random_user_agent.user_agent import UserAgent


class LattesCV(Spider):
    name = "lattes"
    ua = UserAgent()
    basse_url = "https://buscatextual.cnpq.br/buscatextual"

    default_headers = {"User-Agent": ua.get_random_user_agent()}
    start_urls = [
        f"{basse_url}/busca.do?metodo=forwardPaginaResultados&registros=0;100&query=%28+%2Bidx_nacionalidade%3Ae%29+or+%28+%2Bidx_nacionalidade%3Ab+%5E500+%29&analise=cv&tipoOrdenacao=null&paginaOrigem=index.do&mostrarScore=true&mostrarBandeira=true&modoIndAdhoc=null"
    ]

    def start_requests(self, response: Response):
        query_results = response.css(".tit_form b::text").get()
        results_per_page = 100

        pages = query_results // results_per_page
        for i in range(0, pages):
            yield Request(
                url=f"{self.basse_url}/busca.do?metodo=forwardPaginaResultados&registros={i*results_per_page};{results_per_page}&query=%28+%2Bidx_nacionalidade%3Ae%29+or+%28+%2Bidx_nacionalidade%3Ab+%5E500+%29&analise=cv&tipoOrdenacao=null&paginaOrigem=index.do&mostrarScore=true&mostrarBandeira=true&modoIndAdhoc=null",
                headers=self.default_headers,
                callback=self.parse_preview,
            )

    def parse_preview(self, response: Response):
        scripts = response.css(".resultado li b")
        for script in scripts:
            name = script.css("a::text").get()
            url = script.css("a::attr(href)").get()
            cv_id = url.split("('")[1].split("'")[0]
            previw_cv_url = f"{self.basse_url}/preview.do?metodo=apresentar&id={cv_id}"

            yield Request(
                url=previw_cv_url,
                headers=self.default_headers,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_context": "first",
                    "playwright_page_methods": [
                        PageMethod("evaluate", "abreCV();"),
                    ],
                    "cv_name": name,
                    "cv_id": cv_id,
                },
                callback=self.handle_popup,
            )

    async def handle_popup(self, response):
        page: Page = response.meta["playwright_page"]

        popup = await page.wait_for_event("popup")

        await popup.wait_for_load_state("domcontentloaded")
        await popup.wait_for_selector("body", timeout=5000)

        cv = await popup.content()

        await popup.close()
        await page.close()

        cv_name = response.meta["cv_name"]
        cv_id = response.meta["cv_id"]
        with open(f"./r/{cv_name}-{cv_id}.html", "w") as f:
            f.write(cv)


process = CrawlerProcess(
    settings={
        "FEEDS": {
            "items.json": {"format": "json", "encoding": "utf8"},
        },
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_BROWSER_TYPE": "firefox",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "timeout": 30000,
        },
        "PLAYWRIGHT_CONTEXTS": {
            "first": {
                "user_data_dir": "./playwright_data",
            }
        },
        "PLAYWRIGHT_ABORT_ON_CLOSED_PAGE": False,
    }
)


process.crawl(LattesCV)
process.start()
