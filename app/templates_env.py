import calendar
import markdown as md
from jinja2 import Markup
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
templates.env.filters["month_name"] = lambda m: calendar.month_name[m]
templates.env.filters["markdown"] = lambda text: Markup(md.markdown(text or "", extensions=["nl2br"]))
