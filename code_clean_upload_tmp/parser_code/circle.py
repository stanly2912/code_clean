def get_circle(body):
    """
    获取函数体中的圈复杂度
    :param body:
    :return:
    """
    circle = 0
    statements = []
    # circle_type = ["if_statement", "for_statement", "while_statement", "try_statement", "conditional_expression"]
    if not body:
        return circle, []
    for child in body.children:
        if child.type == "if_statement":
            # print(child)
            circle += 1
            statements.append(child)
        if child.type == "for_statement":
            # print(child)
            circle += 1
            statements.append(child)
        if child.type == "while_statement":
            # print(child)
            circle += 1
            statements.append(child)
        if child.type == "boolean_operator":
            """ and or """
            # print(child)
            circle += 1
            statements.append(child)
        if child.type == "try_statement":
            # print(child)
            circle += 1
            statements.append(child)
        if child.type == "conditional_expression":
            """ 三元运算符 a if a > b else b """
            circle += 1
            statements.append(child)
        if child.type == "ternary_expression":
            """ 三元运算符 a if a > b else b """
            circle += 1
            statements.append(child)
        sub_circle, sub_statements = get_circle(child)
        circle += sub_circle
        statements.extend(sub_statements)
    return circle, statements


if __name__ == '__main__':
    pass
