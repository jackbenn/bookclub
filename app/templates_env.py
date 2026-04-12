import calendar
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
templates.env.filters["month_name"] = lambda m: calendar.month_name[m]
