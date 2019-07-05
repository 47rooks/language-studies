import functools as ft
import math
import pandas as pd

from bokeh.layouts import row
from bokeh.models import ColumnDataSource, FactorRange, Legend, LegendItem
from bokeh.models.widgets import DataTable, DateFormatter, TableColumn
from bokeh.models.tools import HoverTool
from bokeh.palettes import viridis
from bokeh.plotting import figure
from bokeh.transform import dodge

from pathlib import Path

# Store the base path of this file for use in later file lookups
base_path = Path(__file__).parent
text_sizes_path = (base_path / "../data/Text Sizes.csv").resolve()
connectives_path = (base_path / "../data/Text Linguistics Greek Connectives Data.csv").resolve()

# Utility functions for text size data

def get_text_total_sizes():
    """Get the total words for each text in its entirety.
    Returns
      A dataframe with columns Text and 'Total Words'.
    """
    # Get the basic totals - using __ALL__ values
    size_data = pd.read_csv(text_sizes_path)
    total_sizes = size_data.query('Section == \'__ALL__\'') \
                      [['Text','Total Words']].groupby(['Text']).sum()

    # Reset the index for a normal flat df.
    total_sizes.reset_index(inplace=True)

    return total_sizes

def get_author_total_sizes():
    """Get the total words for an author across all texts attributed to each author.
    Returns
      A dataframe with columns Author and 'Total Words'.
    """
    # Get the totals by Author summing from section totals only
    size_data = pd.read_csv(text_sizes_path)
    author_sizes = size_data.query('Section != \'__ALL__\'') \
                       [['Author','Total Words']].groupby(['Author']).sum()

    # Reset the index for a normal flat df.
    author_sizes.reset_index(inplace=True)

    return author_sizes

def get_section_total_sizes():
    """Get the total words by Text/Section.
    Returns
      A dataframe with columns Text, Section and 'Total Words'.
    """
    # Get the section sizes removing the __ALL__ counts.
    size_data = pd.read_csv(text_sizes_path)
    section_sizes = size_data.query('Section != \'__ALL__\'') \
                        [['Text', 'Section', 'Total Words']]

    return section_sizes

# Utility function for connective data

def get_connective_data():
    return pd.read_csv(connectives_path)

def compute_per1000_data(df):
    """Create a per1000 column which computes the ratio of hits per 1000 words
    for each text/section/connective row.
    
    FIXME - modify to handle Text vs Text/Section automatically
    """
    if 'Section' in df.columns and 'Text' in df.columns:
        conn = df[['Text', 'Section', 'Connective', 'Total']].groupby(['Text', 'Section', 'Connective']).sum()
        conn.reset_index(inplace=True)
        conn_with_totals = conn.join(get_section_total_sizes().set_index(['Text', 'Section']), on=['Text', 'Section'])
        conn_with_totals['per1000'] = conn_with_totals.Total * 1000.0 / conn_with_totals['Total Words']
    elif 'Text' in df.columns:
        conn = df[['Text', 'Connective', 'Total']].groupby(['Text', 'Connective']).sum()
        conn.reset_index(inplace=True)
        conn_with_totals = conn.join(get_section_total_sizes().set_index(['Text']), on=['Text'])
    else:
        # Assume here that df contains columns Total and 'Total Words' with whatever keys the caller wants
        conn_with_totals = df
        
    conn_with_totals['per1000'] = conn_with_totals.Total * 1000.0 / conn_with_totals['Total Words']

    return conn_with_totals

def create_qry(texts = [], connectives = []):
    """Create a Pandas query string given lists of texts and connectives
    to search for.

    Arguments
        texts: a dict of Text names to arrays of sections. An empty section array
               results in all sections being returned,
        connectives: an array of the connectives to search for.
    """
    qry_frags = []
    for t in texts.keys():
        if not texts[t]:
            qry_frags.append('Text == \'{}\''.format(t))
        else:
            sections = [ '{}'.format(s) for s in texts[t] ]
            qry_frags.append('(Text == \'{}\' and Section in {})'.format(t, sections))
    return 'Connective in {} and ({})'.format(connectives, ' or '.join(qry_frags))

class CorpusMetrics:

    def __init__(self, texts=None, connectives=None, title=None,
                 x_title=None, y_title=None,
                 x_major_name=None, x_minor_name=None, x_minor_values=[]):
        """Constructor

        Arguments
            texts: dict mapping text name to a list of section names to include in the query.
                   As an example:

                   {'Josephus Greek': [],
                    'LXX Rahlfs Tagged': [],
                    'NA28 GNT': ['1 Acts', '2 Acts', 'Mark', 'Luke', 'Matthew'] }
            connectives: a list of the connectives to include in the query
        """
        self._texts = texts
        self._connectives = connectives
        self._title = title
        self._x_title = x_title
        self._y_title = y_title
        self._x_major_name = x_major_name
        self._x_minor_name = x_minor_name
        self._x_minor_values = x_minor_values

        # Initialize object dataframe
        qry = create_qry(self._texts, self._connectives)

        # Extract data and compute hits per 1000
        data = get_connective_data().query(qry)
        data = compute_per1000_data(data)

        # Get hit data for each text section
        data = data.round({'per1000': 2})
        section_data = data[['Section','Total','Total Words','per1000']]
        section_data.columns = ['Book','Hit Total','Total Words','Hits per 1000']

        # Get hit total for all sections represented for each text
        # Note that for the 'NA28 GNT' this will be a total over Luke, Acts and Matthew only.
        aggs = data.groupby(['Text']).sum()
        aggs.per1000 = aggs.Total * 1000.0 / aggs['Total Words']
        aggs.reset_index(inplace=True)
        aggs = aggs.round({ 'per1000' : 2 })
        aggs.columns = ['Book','Hit Total','Total Words','Hits per 1000']
        all_data = aggs.append(section_data)

        # Sort in canonical order
        ordered_texts = ['LXX Rahlfs Tagged', 'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua', 'Judges',
                        'Ruth', '1Samuel', '2Samuel', '1Kings', '2Kings', '1Chronicles', '2Chronicles', '1Esdras', 'Ezra',
                        'Nehemiah', 'Esther', 'Judith', 'Tobit', '1Maccabees', '2Maccabees', '3Maccabees', '4Maccabees',
                        'Psalms', 'Odes', 'Proverbs', 'Ecclesiastes', 'Song', 'Job', 'Wisdom', 'Sirach', 'Solomon',
                        'Hosea', 'Amos', 'Micah', 'Joel', 'Obadiah', 'Jonah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai',
                        'Zechariah', 'Malachi', 'Isaiah', 'Jeremiah', 'Baruch', 'Lamentations', 'Letterjeremiah', 'Ezekiel',
                        'Daniel', 'Susanna', 'Bel',
                        'Matthew', 'Mark', 'Luke', '1 Acts', '2 Acts',
                        'Josephus Greek', 'Antiq.', 'War', 'Life', 'Apion', 'NA28 GNT']

        # Make the Book column a category with the specified order
        all_data['Book'] = pd.Categorical(all_data['Book'], ordered_texts, True)
        self._all_data_sorted = all_data.sort_values(by=['Book'])

    def blank_index(self):
        """Blank out the index column so that we do not see it in print outs.
        """
        blankIndex=[''] * len(self._display_data)
        self._display_data.index=blankIndex

    def validate_columns(self, df):
        """Verify that the df has the expected columns, which are
        'Book', 'Hit Total', 'Total Words', 'Hits per 1000'.

        Arguments
            df: the DataFrame to be validated

        Returns:
            True if the columns are present and no others are
            Raises exception otherwise
        """
        # Validate incoming df columns
        valid_columns = pd.Index(['Book', 'Hit Total', 'Hits per 1000', 'Total Words'])
        if df.columns.sort_values().equals(valid_columns) is False:
            raise ValueError('df has {}, rather than the required {} columns.'.format(
                            df.columns, valid_columns))

    def compact(self):
        """Compact rows in df where 'Hit Total' == 0 and summarize the Book values for
        consecutive 0 rows by creating a new with Text = first row.Text + '-' + last row.Text,
        and totalling the 'Hit Total' and 'Total Words'.

        self._all_data_sorted is the source dataframe and is assumed to be sorted
        in the desired order and is not sorted again. Thus there may be multiple groups
        of compacted 0 rows. This is by design.

        A new DataFrame is assigned to self._compacted_df. self._all_data_sorted is not
        modified. Any columns beyond those specified will be dropped from the result.

        Arguments
            df: a DataFrame having exactly the following columns, Book, 'Hit Total', 'Total Words'
                and 'Hits per 1000'.
        """
        self.validate_columns(self._all_data_sorted)

        compacted_df = pd.DataFrame(columns=['Book', 'Hit Total', 'Total Words', 'Hits per 1000'])
        compacting = False
        for index, row in self._all_data_sorted.iterrows():
            if compacting is True:
                if row['Hit Total'] == 0:
                    # compact with existing row compaction data
                    c_row['Hit Total'] += row['Hit Total']
                    c_row['Total Words'] += row['Total Words']
                    # store for later in case this is the last row for this compaction
                    c_end_book = row['Book']
                else:
                    # Calculate aggregates, create book entry, publish compacted row followed by
                    # new row which is not to be compacted
                    if c_start_book == c_end_book:
                        c_row['Book'] = c_start_book
                    else:
                        c_row['Book'] = c_start_book + '-' + c_end_book
                    c_row['Hits per 1000'] = c_row['Hit Total'] * 1000.0 / c_row['Total Words']
                    
                    compacted_df = compacted_df.append(c_row)
                    compacted_df = compacted_df.append(row)
                    compacting = False
            else:
                if row['Hit Total'] != 0:
                    compacted_df = compacted_df.append(row)
                else:
                    compacting = True
                    c_row = row
                    c_start_book = c_row['Book']
                    c_end_book = c_row['Book']   # in case there is only one 0 row
        self._display_data = compacted_df

    def set_included_texts(self, include=None):
        """Set the texts, chapters and such to include in the result table.
        
        Arguments
            include: a list of texts/sections to include. The names come from the text
                     book column of the all_data object.
                     FIXME - this needs proper definition.
        """
        self._display_data = self._display_data.query('Book in {}'.format(include))
        self._display_data['Book'] = pd.Categorical(self._display_data['Book'], include, True)
        self._display_data = self._display_data.sort_values(by=['Book'])

    # def formatted_to_string(self):
    #     """Return a formatted string for printing
    #     """
    #     validate_columns(self, df)

    #     formatters = {}
    #     for col in list(df.columns):
    #         if col == 'Book':
    #             max = df[col].str.len().max()
    #             formatters['Book'] = ft.partial(str.format, "{{:<{}s}}".format(max))
    #         elif col in ['Hit Total', 'Total Words']:
    #             formatters[col] = ft.partial(str.format, "{{:>{}.0F}}".format(len(col)-1))
    #         elif col == 'Hits per 1000':
    #             formatters[col] = ft.partial(str.format, "{{:>{}.2F}}".format(len(col)))
    #     return df.to_string(formatters=formatters, justify='left')

    def create_plot(self, x_range, s_data, x_minor_values, colors,
                    chart_title=None, x_title=None, y_title='Occurrences per 1000 words',
                    x_major_name=None, x2_minor_name=None):
        """Create a figure for the specified x_range and data_range.
        
        Arguments:
        x_range the range of major X values
        s_data the subsection per major X value the corresponding value
        x_minor_values the section names in s_data
        colors a color palette for rendering the sections
        chart_title the title for the chart
        x_title the X axis title
        y_title the Y axis title
        
        Return - the figure
        """
        # Tool palette
        TOOLS = "crosshair,pan,wheel_zoom,box_zoom,reset,save"

        # Create ColumnDataSource for plotting
        source = ColumnDataSource(data=s_data)

        # Create basic figure
        p = figure(x_range=x_range, plot_width=900,
                   title=chart_title,
                   tools = TOOLS, toolbar_location='above')

        # Set up tool tips hover
        hover_items = []

        # Plot the vbars
        num_bars = len(x_minor_values)
        positions = num_bars + 2
        pos_width = 1 / positions
        bar_width = 0.8 / positions
        start = -(positions / 2) * pos_width + (pos_width / 2)
        litems = []
        for i, s in enumerate(x_minor_values):
            offset = start + (i + 1) * pos_width
            bars = p.vbar(x=dodge(self._x_major_name, offset, range=p.x_range),
                          top=s, width=bar_width, source=source,
                          fill_color=colors[i])
            # Add legend item for this series
            litems.append(LegendItem(label=s, renderers=[bars]))
            # Add hover tool
            # Note that toggleable is false because each HoverTool gets an icon in the toolbar if it can be toggled
            #  on and off. With large numbers of sections the toolbar is a real mess. For now just turn them off.
            p.add_tools(HoverTool(tooltips=[(self._x_major_name, '@' + self._x_major_name),
                                            (self._x_minor_name, '{}'.format(s)),
                                            ("Total Hits", "@{t" + s + "}"),
                                            ("Hits/1000", "@{" + s + "}")],
                                  renderers=[bars], toggleable=False,
                                  point_policy='follow_mouse'))

        legend = Legend(items = litems, location=(0, 0))
        p.add_layout(legend, 'right')
        
        # Set axis titles
        p.xaxis.axis_label = x_title
        p.yaxis.axis_label = y_title
        p.xaxis.major_label_orientation = math.pi/4

        return p

    def create_display(self):
        """Create a display from the display_table
        """
        # Create Bokeh datatable from self._display_data df
        # bokeh columns
        Columns = [TableColumn(field=Ci, title=Ci) for Ci in self._display_data.columns]
        data_table = DataTable(columns=Columns,
                               source=ColumnDataSource(self._display_data),
                               height_policy='max', index_position=None) # bokeh table

        # Create and display bar chart
        s_data=dict()
        s_data = pd.DataFrame({self._x_major_name: self._display_data.Book,
                               self._x_minor_values[0]: self._display_data['Hits per 1000'],
                               't' + self._x_minor_values[0]: self._display_data['Hit Total']
                              })

        fig = self.create_plot(x_range=list(self._display_data.Book),
                               s_data=s_data,
                               x_minor_values=self._x_minor_values,
                               colors=viridis(1),
                               chart_title=self._title,
                               x_title=self._x_title,
                               y_title=self._y_title
                              )
        return row(data_table, fig)
