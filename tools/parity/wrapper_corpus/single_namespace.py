import math

LIMIT = 2


def area(radius):
    return round(math.pi * radius * radius, LIMIT)


return_values = {"area": area(1)}
