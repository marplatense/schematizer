import copy
import datetime
from decimal import Decimal
import json

import colander
from dateutil import parser
import deform
from sqlalchemy import inspect
from sqlalchemy.orm.properties import RelationshipProperty


class FKType(object):

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self.fk_errors = []

    def serialize(self, node, appstruct):
        import pdb; pdb.set_trace()

    def deserialize(self, node, cstruct):
        if cstruct is not colander.null and cstruct is not None:
            try:
                value = json.loads(cstruct) if self.secondary is not None \
                        else cstruct
            except ValueError:
                    value = cstruct
            finally:
                if not isinstance(value, (list, tuple)):
                    return tuple([value])
                else:
                    return tuple(value)
        else:
            return colander.null

    def cstruct_children(self, node, cstruct):
            return []


class mDate(colander.Date):

    def deserialize(self, node, cstruct):
        if cstruct is not colander.null:
            if isinstance(cstruct, datetime.date):
                return cstruct
            elif isinstance(cstruct, str):
                return parser.parse(cstruct)
            else:
                raise(colander.Invalid(node, '{0} cannot be parsed to date'.
                                       format(cstruct)))
        else:
            return None


class CommonBehavior(object):

    def __init__(self):
        self._pks = [x.name for x in i.mapper.primary_key]

    def __repr__(self):
        return "<{0}({1})>".format(self.__class__.__name__,
                                   self.__serialize__())

    def __json__(self):
        return json.dumps(self.__serialize__())

    def __serialize__(self):
        cstruct = {}
        i = inspect(self)
        for name, desc in i.mapper.columns.items():
            #if desc.info.get('repr', False):
            cstruct[name] = getattr(self, name)
        return cstruct

    def __get_or_log_error(self, typ, session, value):
        rst = session.query(typ.klass).get(value)
        if rst is None:
                typ.fk_errors.append('"{0}" is not a valid {1}'.
                                     format(value[0] if isinstance(value, tuple)
                                            else value, typ.klass.__name__))
        return rst

    def _preparer_fk(self, value):
        ses = self.schema.bindings['session']
        for every in [x for x in self.schema.children if isinstance(x.typ, FKType)]:
            for pos, pk in enumerate(every.typ.primary_key):
                if value[every.name] is colander.null:
                    if every.typ.secondary is not None:
                        value[every.name] = []
                    else:
                        value[every.typ.local_col[pos]] = None
                        value[every.name] = None
                else:
                    if every.typ.secondary is not None:
                        obj_ = []
                        for ev in value[every.name]:
                            rst = self.__get_or_log_error(every.typ, ses, ev)
                            if rst is not None:
                                obj_.append(rst)
                        value[every.name] = obj_
                    else:
                        value[every.name] = self.__get_or_log_error(every.typ, ses, value[every.name])
                        value[every.typ.local_col[pos]] = getattr(value[every.name], pk.name, None)
        return value

    def __validator_pk(self, node, value):
        ses = self.schema.bindings['session']
        if hasattr(self, '_pks'):
            qry = []
            for pk in self._pks:
                qry.append(value[pk])
        else:
            qry = value
        pk = ses.query(self.__class__).get(qry)
        if pk is not None:
            raise(colander.Invalid(node, '{0} already exists'.format(qry)))
        else:
            return None

    def __validator_fk(self,  node, value):
        errors = []
        for child in self.schema.children:
            if hasattr(child.typ, 'fk_errors') and len(child.typ.fk_errors) > 0:
                errors.append(colander.Invalid(child, "; ".join([err_ for err_ in child.typ.fk_errors])[2:]))
            if hasattr(child, 'foreign_key'):
                if hasattr(child, 'missing_flag') and not child.missing_flag:
                    if value[child.name] is None:
                        errors.append(colander.Invalid(child, 'Attribute {0} is defined '
                                               'as required but no acceptable  value has been '
                                               'set from its relationship'.format(
                                                   child.name)))
        if len(errors)>0:
            error = colander.Invalid(node, '')
            error.children = errors
            raise(error)
        else:
            return None

    def __validator_uk(self, node, value):
        ses = self.schema.bindings['session']
        if value is not None or value is not colander.null:
            q = ses.query(self.__class__).filter(getattr(self.__class__, node.name)==value).all()
        if len(q)!=0:
            raise(colander.Invalid(node, '{0} already exists'.format(value)))
        else:
            return None

    def __build_schema(self, i, name, desc):
        validators = []
        kwargs = {}
        df = copy.copy(desc.info.get('colander', {}))
        try:
            dt = desc.type.__class__.__name__
        except AttributeError:
            dt = FKType
        if hasattr(desc, 'primary_key') and desc.primary_key:
            if desc.autoincrement:
                df['missing'] = colander.drop
            else:
                if len(i.mapper.primary_key) == 1:
                    validators.append(self.__validator_pk)
                else:
                    if not hasattr(self, '_pks'):
                        self.schema.validator.append(self.__validator_pk)
        if 'description' not in df:
            df['description'] = desc.doc
        if 'typ' not in df:
            if dt == 'Enum':
                validators.append(colander.OneOf(desc.type.enums))
                if any([isinstance(x, str) for x in desc.type.enums]):
                    df['typ'] = colander.String()
                else:
                    if all([isinstance(x, int) for x in desc.type.enums]):
                        df['typ'] = colander.Int()
                    elif all([isinstance(x, float) for x in desc.type.enums]):
                        df['typ'] = colander.Float()
                    elif all([isinstance(x, Decimal) for x in desc.type.enums]):
                        df['typ'] = colander.Decimal()
                    else:
                        raise(NotImplementedError('We could not cast this Enum to any '
                                                  'valid data type'))
            elif dt in ('Date', 'DateTime'):
                df['typ'] = mDate()
            else:
                try:
                    df['typ'] = getattr(colander, dt)()
                except AttributeError:
                    if dt=='Text':
                        df['typ'] = colander.String()
                    else:
                        raise(NotImplementedError('Datatype {0} not mapped'.format(dt)))
                if dt=='String' and desc.type.length>0:
                    validators.append(colander.Length(1, desc.type.length))
        if hasattr(desc, 'unique') and desc.unique and not desc.primary_key:
            validators.append(self.__validator_uk)
        if 'missing' not in df and \
           (hasattr(desc, 'foreign_keys') and len(desc.foreign_keys)==0):
            if hasattr(desc, 'nullable'):
                if desc.default is not None:
                    df['missing'] = desc.default.arg
                else:
                    df['missing'] = colander.null if desc.nullable else colander.required
            else:
                df['missing'] = colander.null
        if hasattr(desc, 'default') and desc.default is not None:
            df['default'] = desc.default.arg
        else:
            df.pop('default', None)
        if hasattr(desc, 'foreign_keys') and len(desc.foreign_keys)>0:
            # it is a pk and fk at the same time
            kwargs['foreign_key'] = True
            if (hasattr(desc, 'primary_key') and desc.primary_key) or \
               (hasattr(desc, 'nullable') and not desc.nullable):
                kwargs['missing_flag'] = False
        if 'widget' not in df:
            # TODO: set switch case with all widgets
            if dt == 'Enum':
                df['widget'] = deform.widget.SelectWidget(
                                    values=sorted([(x,x) for x in desc.type.enums]))
            elif dt == 'Text':
                df['widget'] = deform.widget.TextAreaWidget()
        if 'colander' in desc.info and \
           'validator'  in desc.info['colander']:
            validators += desc.info['colander']['validator']
        if len(validators)==1:
            df['validator'] = validators[0]
        elif len(validators)>1:
            df['validator'] = colander.All(*validators)
        return colander.SchemaNode(name=name, typ=df['typ'],
                                   default=df.get('default', None),
                                   missing=df.get('missing', colander.null),
                                   preparer=df.get('preparer', None),
                                   validator=df.get('validator', None),
                                   title=df.get('title', None),
                                   description=df.get('description', None),
                                   widget=df.get('widget', None), **kwargs)

    def __schema__(self):
        """Build schema colander based on the data from each attribute plus \
what we can get from the 'colander' key"""
        self.schema = colander.SchemaNode(colander.Mapping())
        self.schema.validator = []
        i = inspect(self)
        for name, desc in i.mapper.columns.items() + \
                          i.mapper.relationships.items():
            if name in i.mapper.columns and \
               i.mapper.columns[name].info.get('repr') and \
               not i.mapper.columns[name].info['repr']:
                continue
            elif isinstance(desc, RelationshipProperty):
                pk = {'klass':desc.mapper.class_,
                      'primary_key':desc.mapper.primary_key,
                      'local_col':[x.name for x in desc.local_columns],
                      'secondary':desc.secondary,
                     }
                try:
                    desc.info['colander']['typ'] = FKType(**pk)
                except KeyError:
                    desc.info['colander'] = {'typ':FKType(**pk)}
                if 'widget' not in desc.info['colander']:
                    # TODO: missing methods here:
                    # we have to decide if we use a regular select box (for tables with
                    # few items) or an autocomplete widget (for multiple elements)
                    pass
            self.schema.add(self.__build_schema(i, name, desc))
        self.schema.name = self.__class__.__name__
        self.schema.preparer = self._preparer_fk
        self.schema.validator.append(self.__validator_fk)
        if len(self.schema.validator)==1:
            self.schema.validator = self.schema.validator[0]
        else:
            self.schema.validator = colander.All(*self.schema.validator)

def generic_init(self, session, **kw):
    self.__schema__()
    # we bind the session
    self.schema = self.schema.bind(session=session)
    if len(kw)>0:
        appstruct = self.schema.deserialize(kw)
        for k, v in appstruct.items():
            setattr(self, k, v)

