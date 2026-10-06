import calendar
import markdown as md
from markupsafe import Markup
from fastapi.templating import Jinja2Templates

from app.sort_keys import author_sort_key, title_sort_key

templates = Jinja2Templates(directory="app/templates")
templates.env.filters["month_name"] = lambda m: calendar.month_name[m]
templates.env.filters["dateformat"] = lambda d, fmt="%B %-d, %Y": d.strftime(fmt) if d else ""
templates.env.filters["markdown"] = lambda text: Markup(md.markdown(text or "", extensions=["nl2br"]))
templates.env.filters["author_sort"] = author_sort_key
templates.env.filters["title_sort"] = title_sort_key
