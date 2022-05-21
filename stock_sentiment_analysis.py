import stock_funcs as sf
import dash
from dash import html
from dash import dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import pandas as pd

## WEB APP ##
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.layout = html.Div(children=[
    html.H1(children='Stock Sentiment'),

    html.Div([
        dcc.Input(id='ticker', type='text', value='TICKER'),
        html.Button(id='submit-button-state', n_clicks=0, children='Submit'),
    ]),

    html.Div(id='output'),

    html.Div([
        dcc.Graph(id='stock-data'),
    ]),

    # Hidden div inside the app that stores the intermediate value
    html.Div(id='intermediate-value', style={'display': 'none'})
    ])


@app.callback(Output('output', 'children'),
              [Input('submit-button-state', 'n_clicks')],
              [Input('intermediate-value', 'children')],
              [State('ticker', 'value')])
def invalid_ticker(n_clicks, value, ticker):
    if ticker == 'TICKER':
        return ''
    if value is None:
        return 'cannot get data for ' + ticker


@app.callback(Output('intermediate-value', 'children'),
              [Input('submit-button-state', 'n_clicks')],
              [State('ticker', 'value')])
def get_data(n_clicks, ticker):
    if n_clicks > 0:
        # call func to get data
        data = sf.run_sentiment(ticker)
        df = data.to_json(date_format='iso', orient='split', index=False)
        return df


@app.callback(Output('stock-data', 'figure'),
              [Input('intermediate-value', 'children')],
              [State('ticker', 'value')])
def update_graph(data, ticker):
    if data is None:
        raise PreventUpdate

    # load data into dataframe
    df = pd.read_json(data, orient='split')
    if df.empty:
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    dates = list(df['date'])

    # Create and style traces
    fig.add_trace(go.Scatter(x=dates, y=df['news'], name='News',
                             line=dict(color='firebrick')), secondary_y=True, )
    fig.add_trace(go.Scatter(x=dates, y=df['reddit'], name='Reddit',
                             line=dict(color='royalblue')), secondary_y=True, )
    fig.add_trace(go.Scatter(x=dates, y=df['twitter'], name='socialsentiment.io',
                             line=dict(color='orange')), secondary_y=True, )
    # fig.add_trace(go.Scatter(x=dates, y=df['mean'], name='Mean',
    #                         line=dict(color='orange')), secondary_y=True, )
    fig.add_trace(go.Scatter(x=dates, y=df['close'], name='Price',
                             line=dict(color='black')),
                  secondary_y=False, )  # dash options include 'dash', 'dot', and 'dashdot'

    # Add figure title
    fig.update_layout(title_text=ticker)

    # Set y-axes titles
    fig.update_yaxes(title_text="Price", secondary_y=False)
    fig.update_yaxes(title_text="Negative <- Sentiment -> Positive", secondary_y=True)
    fig.update_yaxes(tickprefix="$", secondary_y=False)

    fig.update_yaxes(range=[-1, 1], secondary_y=True)

    return fig


if __name__ == '__main__':
    app.run_server(debug=True)
