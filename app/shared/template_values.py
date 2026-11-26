"""Keep absent values empty in rendered user interfaces."""


def finalize_template_value(value):
    return "" if value is None else value
