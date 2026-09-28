import ast,operator as op
A={ast.Add:op.add,ast.Sub:op.sub,ast.Mult:op.mul,ast.Div:op.truediv,ast.Mod:op.mod,ast.Pow:op.pow,ast.USub:op.neg,ast.UAdd:op.pos}
def ev(n):
    if isinstance(n,ast.Expression):return ev(n.body)
    if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)):return n.value
    if isinstance(n,ast.UnaryOp) and type(n.op) in A:return A[type(n.op)](ev(n.operand))
    if isinstance(n,ast.BinOp) and type(n.op) in A:
        b=ev(n.right)
        if isinstance(n.op,ast.Pow) and abs(b)>100:raise ValueError("Exponent too large")
        return A[type(n.op)](ev(n.left),b)
    raise ValueError("Unsupported expression")
def calculate(expression):return {"expression":expression,"result":ev(ast.parse(expression,mode="eval"))}
