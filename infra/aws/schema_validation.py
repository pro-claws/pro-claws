"""Narrow schema comparison for documented PostgreSQL literal-array casts."""
import copy
import re


_LITERAL=r"'(?:''|[^'])*'::character varying"
_ARRAY=re.compile(r'\(ARRAY\[('+_LITERAL+r'(?:,\s*'+_LITERAL+r')*)\]\)::text\[\]')


def normalize_literal_array_casts(sql):
    """Only distribute varchar-literal array -> text casts, outside strings.

    PostgreSQL documents ARRAY[...]::type[] as casting each element to type.
    Do not normalize operators, identifiers, values, other casts or predicates.
    """
    result=[];index=0
    while index<len(sql):
        match=_ARRAY.match(sql,index)
        if match:
            items=re.findall(_LITERAL,match.group(1))
            result.append('ARRAY['+', '.join('('+item+')::text' for item in items)+']')
            index=match.end();continue
        if sql[index] in ("'",'"'):
            quote=sql[index];start=index;escaped=quote=="'" and index>0 and sql[index-1] in 'eE' and (index<2 or not (sql[index-2].isalnum() or sql[index-2]=='_'))
            index+=1
            while index<len(sql):
                if escaped and sql[index]=='\\':index+=2;continue
                if sql[index]==quote:
                    index+=1
                    if index<len(sql) and sql[index]==quote:index+=1;continue
                    break
                index+=1
            result.append(sql[start:index]);continue
        result.append(sql[index]);index+=1
    return ''.join(result)


def comparable(inventory):
    result=copy.deepcopy(inventory)
    for field in ('constraints','indexes'):
        for row in result[field]:row[-1]=normalize_literal_array_casts(row[-1])
    return result
