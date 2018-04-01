import dash_html_components as html
import dash_core_components as dcc

import propnet.models as models

from propnet.symbols import DEFAULT_SYMBOL_TYPES
from propnet.web.utils import references_to_markdown


# layouts for model detail pages

def model_image_component(model):
    """
    Get a Robohash of a provided model, to give a
    face to a name.

    Args:
      model: instance of an AbstractModel subclass

    Returns: a Dash Img element

    """
    url = "https://robohash.org/{}".format(model.__hash__())
    return html.Img(src=url, style={'width': 150, 'border-radius': '50%'})


def model_layout(model_name):
    """Create a Dash layout for a provided model.

    Args:
      model: an instance of an AbstractModel subclass

    Returns:
      Dash layout

    """

    # instantiate model from name
    model = getattr(models, model_name)()

    if model.tags:
        tags = html.Ul(className="tags", children=[
            html.Li(tag, className="tag") for tag in model.tags
        ])
    else:
        tags = None

    badge = html.Div(className='double-val-label', children=[
        html.Span('model-id', className='model'),
        html.Span('{}'.format(model.model_id))
    ])

    title = html.Div(className='row', children=[
        html.Div(className='three columns', style={'text-align': 'right'}, children=[
            model_image_component(model)
        ]),
        html.Div(className='nine columns', children=[
            html.H3(model.title),
            badge
        ])
    ])

    #if model.references:
    #    references = dcc.Markdown(references_to_markdown(model.references))
    #else:
    #    # TODO: append to list instead ...
    #    references = None

    references = None

    symbols_layout = html.Div(children=[
        html.Div(className='row', children=[
            html.Div(className='two columns', children=[str(symbol)]),
            html.Div(className='ten columns', children=[
                dcc.Link(DEFAULT_SYMBOL_TYPES[symbol_name].display_names[0],
                         href='/property/{}'.format(symbol_name))])
        ])
        for symbol, symbol_name in model.symbol_mapping.items()
    ])

    # method = model.method TODO: add below description

    # TODO
    breadcrumb = html.Div()

    if hasattr(model, 'equations'):
        # TODO: change equations to property
        equations_layout = html.Div(children=[html.H6('Equations'),
                                              html.Div(children=[
                                                  html.Div(className='row', children=[equation])
                                                  for equation in model.equations
                                              ])])
    else:
        equations_layout = html.Div()

    return html.Div([
        breadcrumb,
        title,
        html.Br(),
        html.H6('References'),
        references,
        html.H6('Symbols'),
        symbols_layout,
        equations_layout,
        html.H6('What this model does'),
        dcc.Markdown(model.description),
        # dcc.Markdown("Method: {}".format(model.method)),
        #html.H6('Dimensional analysis'),
        html.H6('Tags'),
        tags
    ])


model_links = {}
for model_name in models.DEFAULT_MODEL_NAMES:
    # instantiate model from name
    model = getattr(models, model_name)()

    # group by tag
    tags = model.tags

    for tag in tags:
        if tag not in model_links:
            model_links[tag] = []

    for tag in tags:

        passes = model.test()
        passes = "✅" if passes else "❌"

        link_text = "{}".format(model.title)

        model_links[tag].append(
            html.Div([
                html.Span('{} '.format(passes)),
                dcc.Link(link_text,
                         href='/model/{}'.format(model_name)),
                html.Br()
            ])
        )

model_links_grouped = []
for tag, links in model_links.items():
    model_links_grouped += [
        html.H6(tag.title()),
        html.Div(links),
        html.Br()
    ]

models_index = html.Div([
    html.H5('Current models:'),
    html.Div(model_links_grouped),
    html.Br(),
    dcc.Link('< Back', href='/')
])
