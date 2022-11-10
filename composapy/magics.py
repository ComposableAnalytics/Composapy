from IPython.core.magic import register_line_cell_magic


@register_line_cell_magic
def sql(line, cell=None):
    from composapy.queryview.api import QueryView

    driver = QueryView.driver()

    if cell is None:
        return driver.run(line)
    else:
        return driver.run("".join(cell))
