from IPython.core.magic import register_line_cell_magic

from composapy.queryview.api import QueryView


@register_line_cell_magic
def sql(line, cell=None):
    driver = QueryView.driver()

    if cell is None:
        return driver.run(line)
    else:
        return driver.run("".join(cell))
