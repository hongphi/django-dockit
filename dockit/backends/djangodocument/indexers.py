from django.db.models import Model

from dockit.backends.indexer import BaseIndex
from dockit.schema import fields#, Document

from models import DocumentStore, StringIndex, IntegerIndex, DateIndex
from backend import ModelDocumentStorage, DocumentQuery

class Indexer(object):
    def __init__(self, doc_class, index_creator, dotpath):
        self.doc_class = doc_class
        self.index_creator = index_creator
        self.dotpath = dotpath
    
    def __call__(self, document):
        try:
            value = document.dot_notation(self.dotpath)
        except (KeyError, IndexError):
            return
        
        if isinstance(value, list):
            for val in value:
                print val
                self.index_creator(document.pk, self.dotpath, val)
        else:
            self.index_creator(document.pk, self.dotpath, value)


class ExactIndex(BaseIndex):
    '''
    register_indexer(backend, "equals", index_cls)

    Book.objects.enable_index("equals", "author_name", {'field':'author_name'})
    Book.objects.filter.author_name('Mark Twain')
    Book.objects.values.author_name()
    '''
    INDEXES = [(fields.TextField, StringIndex),
           (fields.IntegerField, IntegerIndex),
           #(fields.SchemaField, TextIndex), #unsoported
           #(fields.ListField, None), #multi key index
           #(fields.DictField, None), #multi key index
           #(Document, StringIndex),
           (Model, StringIndex),
           (fields.ReferenceField, StringIndex),
           (fields.ModelReferenceField, StringIndex),]
    
    def __init__(self, *args, **kwargs):
        super(ExactIndex, self).__init__(*args, **kwargs)
        self.dotpath = self.params.get('field', self.params.get('dotpath'))
        self.generate_index()
    
    def generate_index(self):
        collection = self.document._meta.collection
        field = self.document.dot_notation_to_field(self.dotpath)
        
        subindex = self._lookup_index(field)
        if subindex is None and hasattr(field, 'schema'):
            subindex = self._lookup_index(field.schema)
        
        func = Indexer(self.document, subindex.objects.db_index, self.dotpath)
        filt = subindex.objects.filter_kwargs_for_value
        unique_values = subindex.objects.unique_values
        clear = subindex.objects.clear_db_index
        
        self.index_functions = {'map':func, 'filter':filt, 'unique_values':unique_values, 'clear':clear}
    
    def _lookup_index(self, field):
        for key, val in self.INDEXES:
            if isinstance(field, key):
                return val
    
    def on_document_save(self, instance):
        self.index_functions['map'](instance)
    
    def on_document_delete(self, instance):
        self.index_functions['clear'](instance)
        
    def filter(self, value):
        qs = DocumentStore.objects.filter(collection=self.collection)
        qs = qs.filter(**self.index_functions['filter'](self.name, value))
        return DocumentQuery(qs, self.document)
    
    def values(self):
        return self.indexes[self.collection][dotpath]['unique_values']()

ModelDocumentStorage.register_indexer("equals", ExactIndex)

class DateIndex(BaseIndex):
    def __init__(self, *args, **kwargs):
        super(ExactIndex, self).__init__(*args, **kwargs)
        self.dotpath = self.params.get('field', self.params.get('dotpath'))
        self.generate_index()
        
    def generate_index(self):
        collection = self.document._meta.collection
        field = self.document.dot_notation_to_field(self.dotpath)
        
        subindex = DateIndex
        
        func = Indexer(self.document, subindex.objects.db_index, self.dotpath)
        filt = subindex.objects.filter_kwargs_for_value
        unique_values = subindex.objects.unique_values
        clear = subindex.objects.clear_db_index
        
        self.index_functions = {'map':func, 'filter':filt, 'unique_values':unique_values, 'clear':clear}
    
    def filter(self, *args, **kwargs):
        qs = DocumentStore.objects.filter(collection=self.collection)
        filter_func = self.index_functions['filter']
        if args:
            qs = qs.filter(**filter_func('%s__in' % self.name, args))
        for key, value in kwargs.iteritems():
            qs = qs.filter(**filter_func('%s__%s' % (self.name, key), value))
            
        return DocumentQuery(qs, self.document)
    
    def values(self, *args, **kwargs):
        qs = DocumentStore.objects.filter(collection=self.collection)
        filter_func = self.index_functions['filter']
        if args:
            qs = qs.filter(**filter_func('%s__in' % self.name, args))
        for key, value in kwargs.iteritems():
            qs = qs.filter(**filter_func('%s__%s' % (self.name, key), value))
        return qs.values_list('value', flat=True).distinct()

ModelDocumentStorage.register_indexer("date", DateIndex)
