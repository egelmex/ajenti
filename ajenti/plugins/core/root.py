import re

from ajenti.ui import UI
from ajenti.com import *
from ajenti import version
from ajenti.app.api import ICategoryProvider, IContentProvider
from ajenti.ui.template import BasicTemplate
from ajenti.app.helpers import EventProcessor, event
from ajenti.app.urlhandler import URLHandler, url, get_environment_vars

class RootDispatcher(URLHandler, EventProcessor, Plugin):

    categories = Interface(ICategoryProvider)
    folders = {
        'top': '',
        'system': 'System',
        'apps': 'Applications',
        'servers': 'Servers',
        'other': 'Other',
        'bottom': ''
    }
    folder_ids = ['top', 'system', 'apps', 'servers', 'other', 'bottom']
    
    def main_ui(self):
        templ = self.app.get_template('main.xml')

        cat_selected = self.app.session.get('cat_selected', 'Dashboard')

        cat = None
        v = UI.VContainer(spacing=0)
        
        cats = self.categories
        cats = sorted(cats, key=lambda p: p.text)

        for fld in self.folder_ids:
            cat_vc = UI.VContainer(spacing=0)
            if self.folders[fld] == '':
                cat_folder = cat_vc # Omit wrapper for special folders
            else:
                cat_folder = UI.CategoryFolder(
                                cat_vc,
                                text=self.folders[fld],
                                icon='/dl/core/ui/catfolders/'+ fld + '.png'
                                    if self.folders[fld] != '' else '',
                                id=fld
                             )
            exp = False
            empty = True
            for c in cats:
                if c.folder == fld:
                    empty = False
                    if c.get_name() == cat_selected:
                        cat_vc.vnode(UI.Category(c.category, id=c.get_name(), selected='true'))
                        cat = c
                        exp = True
                    else:
                        cat_vc.vnode(UI.Category(c.category, id=c.get_name()))

            if not empty: v.vnode(cat_folder)
            cat_folder['expanded'] = exp
            
        templ.appendChildInto('leftplaceholder', v)
        templ.appendChildInto('rightplaceholder', cat.get_ui())
        templ.appendChildInto('version', UI.Label(text='Ajenti '+version))
        templ.appendChildInto('links', 
            UI.HContainer(
                UI.OutLinkLabel(text='About', url='http://wiki.github.com/Eugeny/ajenti/'),
                UI.OutLinkLabel(text='License', url='http://eugeny.github.com/ajenti/license/')
            ))
            

        return templ

    def do_init(self):
        cat_selected = self.app.session.get('cat_selected', 'Dashboard')
        cat = None
        for c in self.categories:
            if c.get_name() == cat_selected:
                cat = c
        cat.on_init()

    @url('^/$')
    def process(self, req, start_response):
        templ = self.app.get_template('index.xml')

        self.do_init()
        main = self.main_ui()

        templ.appendChildInto('body', main.elements())

        return templ.render()

    @url('^/session_reset$')
    def process_reset(self, req, start_response):
        self.app.session.clear()
        start_response('301 Moved Permanently', [('Location', '/')])
        return ''

    @event('category/click')
    def handle_category(self, event, params, **kw):
        if not isinstance(params, list):
            return
        if len(params) != 1:
            return

        self.app.session['cat_selected'] = params[0]
        self.do_init()

    @url('^/handle/.+')
    def handle_generic(self, req, start_response):
        # Iterate through the IEventDispatchers and find someone who will take care of the event
        # TODO: use regexp for shorter event names, ex. 'btn_clickme/click'
        path = req['PATH_INFO'].split('/')
        event = '/'.join(path[2:4])
        params = path[4:]

        self.do_init()

        # Current module
        cat = filter(lambda x: x.get_name() == self.app.session.get('cat_selected', 'Dashboard'), self.categories)[0]
        
        # Search self and current category for event handler
        for handler in (cat, self):
            if handler.match_event(event):
                vars = get_environment_vars(req)
                result = handler.event(event, params, vars = vars)
                if isinstance(result, str):
                    # For AJAX calls that do not require information
                    # just return ''
                    return result
                if isinstance(result, BasicTemplate):
                    # Useful for inplace AJAX calls (that returns partial page)
                    return result.render()

        # We have no result or handler - return default page
        main = self.main_ui()

        return main.render()

