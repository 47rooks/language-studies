import functools as ft
import math
import pandas as pd

from bokeh.layouts import gridplot, layout, row
from bokeh.models import ColumnDataSource, CDSView, Legend, LegendItem
from bokeh.models.annotations import Label
from bokeh.models.filters import GroupFilter
from bokeh.models.widgets import DataTable, DateFormatter, TableColumn
from bokeh.models.widgets.markups import Div
from bokeh.models.tools import HoverTool
from bokeh.palettes import viridis
from bokeh.plotting import figure
from bokeh.transform import dodge

from pathlib import Path

# Store the base path of this file for use in later file lookups
base_path = Path(__file__).parent
text_sizes_path = (base_path / "../data/Text Sizes.csv").resolve()
connectives_path = (base_path / "../data/Text Linguistics Greek Features Data.csv").resolve()

# Some module constants
DISPLAY_DF_COLUMNS=['Group', 'Range', 'Feature', 'Count', 'Total Words', 'per1000']
FEATURE_DF_COLUMNS=['Author','Text','Section','Feature','Count','AccWorkspace']
TEXT_SIZE_DF_COLUMNS=['Author','Text','Section','Total Words','IncludedInTotal','AccWorkspace']

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
        conn = df[['Text', 'Section', 'Feature', 'Count']].groupby(['Text', 'Section', 'Feature']).sum()
        conn.reset_index(inplace=True)
        conn_with_totals = conn.join(get_section_total_sizes().set_index(['Text', 'Section']), on=['Text', 'Section'])
        conn_with_totals['per1000'] = conn_with_totals.Count * 1000.0 / conn_with_totals['Total Words']
    elif 'Text' in df.columns:
        conn = df[['Text', 'Feature', 'Count']].groupby(['Text', 'Feature']).sum()
        conn.reset_index(inplace=True)
        conn_with_totals = conn.join(get_section_total_sizes().set_index(['Text']), on=['Text'])
    else:
        # Assume here that df contains columns Count and 'Total Words' with whatever keys the caller wants
        conn_with_totals = df
        
    conn_with_totals['per1000'] = conn_with_totals.Count * 1000.0 / conn_with_totals['Total Words']

    return conn_with_totals

def create_qry(texts = [], connectives = []):
    """Create a Pandas query string given lists of texts and connectives
    to search for.

    Arguments
        texts: a dict of Text names to arrays of sections. An empty section array
               results in all sections being returned,
        features: a list of the features to include in the query. The
                     connective names are those drawn from the
                     'Text Linguistics Greek Features Data.csv' file.
    """
    qry_frags = []
    for t in texts.keys():
        if not texts[t]:
            qry_frags.append('Text == \'{}\''.format(t))
        else:
            sections = [ '{}'.format(s) for s in texts[t] ]
            qry_frags.append('(Text == \'{}\' and Section in {})'.format(t, sections))
    return 'Feature in {} and ({})'.format(connectives, ' or '.join(qry_frags))

def get_feature_data(texts, features):
    """Get the requested feature data from the specified texts and sections.

    Arguments
        texts: a dict of Text names to arrays of sections. An empty section array
               results in all sections being returned,
        features: a list of the features to include in the query. The
                     connective names are those drawn from the
                     'Text Linguistics Greek Features Data.csv' file.
    """
    qry = create_qry(texts, features)

    # Extract data and compute hits per 1000
    data = get_connective_data().query(qry)
    data = compute_per1000_data(data)

    # FIXME rounding should be moved
    data = data.round({'per1000': 2})

    return data

def add_total_by_group(data):
    # Get hit total for all sections represented for each text
    aggs = data[['Text', 'Section', 'Feature','Count','Total Words']].groupby(
                   ['Text', 'Feature']).sum()
    aggs.reset_index(inplace=True)
    aggs['per1000'] = aggs.Count * 1000.0 / aggs['Total Words']
    aggs['Section'] = '__ALL__'
    aggs = aggs.round({ 'per1000' : 2 })
    return data.append(aggs, sort=False)

class FeatureMetrics:
    """A FeatureMetrics object contains metrics about features found in texts. It
    contains a list of the texts in which the features are found, the features themselves,
    the total number of occurrences of the features in each text, and the number
    of occurrences per 1000 words of the features in each text.

    It is intended primarily as a display object and provides a way to tabulate and
    plot the data via Bokeh.

    FeatureMetrics supports a major and minor (subordinate) X axis so that one may plot
    bar charts of features by two dimensions. For example one may plot occurrences of
    Greek connectives, by texts, using groups of adjacent ('dodged' in Bokeh terms) bars
    in bar chart. Each group of bars would be for a particular connective and the bars
    in each group would be for a given text. The plot provides mouse hover popups
    showing the current bar's values.
    """
    def __init__(self, df=None, title=None,
                 x_title=None, y_title=None,
                 x_major_name=None, x_minor_name=None,
                 column_display_names=[]):
        """Constructor

        Arguments
            df: A DataFrame containing the data to be displayed. It is assumed to have
                the following columns : Group, Range, Feature, Count, Total Words, per1000
            title: A string for the title for the plot
            x_title: A string for the X-axis title
            y_title: A string for the Y-axis title
            x_major_name: A string with the name of the major X axis
            x_minor_name: A name for subordinate data series for the X axis if required
            column_display_names: The names to be used in the data table display and chart,
                                  replacing the column names in df. Must be ordered in
                                  the same order as the columns in df.
        """
        self._df = df
        self._title = title
        self._x_title = x_title
        self._y_title = y_title
        self._x_major_name = x_major_name
        self._x_minor_name = x_minor_name
        self._column_display_names = column_display_names

        self._colors = viridis(len(self._df[self._x_minor_name].unique()))
        self.sort()

    def sort(self):
        # Sort in canonical order
        ordered_groups = ['LXX Rahlfs Tagged','NA28 GNT','Josephus Greek']
        ordered_texts = ['__ALL__', 'LXX Rahlfs Tagged', 'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua', 'Judges',
                        'Ruth', '1Samuel', '2Samuel', '1Kings', '2Kings', '1Chronicles', '2Chronicles', '1Esdras', 'Ezra',
                        'Nehemiah', 'Esther', 'Judith', 'Tobit', '1Maccabees', '2Maccabees', '3Maccabees', '4Maccabees',
                        'Psalms', 'Odes', 'Proverbs', 'Ecclesiastes', 'Song', 'Job', 'Wisdom', 'Sirach', 'Solomon',
                        'Hosea', 'Amos', 'Micah', 'Joel', 'Obadiah', 'Jonah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai',
                        'Zechariah', 'Malachi', 'Isaiah', 'Jeremiah', 'Baruch', 'Lamentations', 'Letterjeremiah', 'Ezekiel',
                        'Daniel', 'Susanna', 'Bel',
                        'NA28 GNT', 'Matthew', 'Mark', 'Luke', '1 Acts', '2 Acts',
                        'Josephus Greek', 'Antiq.', 'War', 'Life', 'Apion']

        # Suppress Pandas SettingWithCopyWarning as there are false positive cases which
        # the following code can hit with multi-valued Feature data
        pd.options.mode.chained_assignment = None

        # Make the Group column a category with the specified order
        group_cat = pd.Categorical(self._df['Group'].unique(), ordered_groups, True)
        self._df.loc[:, 'Group'] = self._df['Group'].astype(group_cat)

        # Make the Range column a category with the specified order
        range_cat = pd.Categorical(self._df['Range'].unique(), ordered_texts, True)
        self._df.loc[:, 'Range'] = self._df['Range'].astype(range_cat)

        # Sort the rows according to the canonical orders
        self._df = self._df.sort_values(by=['Group', 'Range'])

        # Convert the Categorical columns back now that the sort is done. This just
        # avoids other difficulties with Categoricals.
        self._df.Group = self._df.Group.astype(str)
        self._df.Range = self._df.Range.astype(str)

        # Renable Pandas SettingWithCopyWarning
        pd.options.mode.chained_assignment = 'warn'

    def blank_index(self):
        """Blank out the index column so it is not seen in dataframe prints.
        """
        blankIndex=[''] * len(self._df)
        self._df.index=blankIndex

    def _validate_columns(self, df):
        """Verify that the df has the expected columns, which are
        'Group', 'Range', 'Feature', 'Count', 'per1000'.

        Arguments
            df: the DataFrame to be validated

        Returns:
            True if the columns are present and no others are
            Raises exception otherwise
        """
        # Validate incoming df columns
        valid_columns = pd.Index(DISPLAY_DF_COLUMNS)
        if df.columns.sort_values().equals(valid_columns.sort_values()) is False:
            raise ValueError('df has {}, rather than the required {} columns.'.format(
                             df.columns, valid_columns))

    def compact(self):
        """Compact rows in _df where 'Hit Total' == 0 and summarize the Book values for
        consecutive 0 rows by creating a new with Text = first row.Text + '-' + last row.Text,
        and totalling the 'Hit Total' and 'Total Words'. The data is assumed to be sorted
        in the desired order and is not sorted again. Thus there may be multiple groups
        of compacted 0 rows. This is intended behaviour.
        """
        # self._all_data_sorted is the source dataframe and a new DataFrame is assigned to
        # self._compacted_df. self._all_data_sorted is not modified. Any columns beyond
        # those specified will be dropped from the result.
        self._validate_columns(self._df)

        compacted_df = pd.DataFrame(columns=DISPLAY_DF_COLUMNS)
        compacting = False
        for index, row in self._df.iterrows():
            if compacting is True:
                if row['Count'] == 0:
                    # compact with existing row compaction data
                    c_row['Count'] += row['Count']
                    c_row['Total Words'] += row['Total Words']
                    # store for later in case this is the last row for this compaction
                    c_end_book = row['Range']
                else:
                    # Calculate aggregates, create book entry, publish compacted row followed by
                    # new row which is not to be compacted
                    if c_start_book == c_end_book:
                        c_row['Range'] = c_start_book
                    else:
                        c_row['Range'] = c_start_book + '-' + c_end_book
                    c_row['per1000'] = c_row['Count'] * 1000.0 / c_row['Total Words']
                    
                    compacted_df = compacted_df.append(c_row)
                    compacted_df = compacted_df.append(row)
                    compacting = False
            else:
                if row['Count'] != 0:
                    compacted_df = compacted_df.append(row)
                else:
                    compacting = True
                    c_row = row
                    c_start_book = c_row['Range']
                    c_end_book = c_row['Range']   # in case there is only one 0 row
        self._df = compacted_df

    def set_included_texts(self, include=None):
        """Set the texts, chapters and such to include in the result table.
        
        Arguments
            include: a list of texts/sections to include. The names are the same as
                     those in the 'Text Sizes.csv' and 
                     'Text Linguistics Greek Features Data.csv' files.
        """
        qry_frags = []
        for t in include.keys():
            if not include[t]:
                qry_frags.append('Group == \'{}\''.format(t))
            else:
                ranges = [ '{}'.format(s) for s in include[t] ]
                qry_frags.append('(Group == \'{}\' and Range in {})'.format(t, ranges))
        qry = ' or '.join(qry_frags)

        self._df = self._df.query(qry)

    def move_group_to_range_ALL(self):
        """Where range is __ALL__ replace it with the Group value. Then drop the Group
        column from display.
        """
        self._df.Range = self._df.Range.where(self._df.Range != '__ALL__', self._df.Group)

    # def formatted_to_string(self):
    #     """Return a formatted string for printing
    #     """
    #     _validate_columns(self, df)

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

    def _create_plot(self, x_range, s_data, x_minor_values, colors,
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
        TOOLS = "crosshair,pan,wheel_zoom,box_zoom,reset,save,tap,box_select"

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
            # Create CDSView for plotting and syncing to the Datatable.
            cds_view=CDSView(source=s_data, filters=[GroupFilter(self._x_minor_name, s)])
            offset = start + (i + 1) * pos_width
            bars = p.vbar(x=dodge(self._x_major_name, offset, range=p.x_range),
                          top='per1000',
                          width=bar_width, source=s_data, view=cds_view,
                          fill_color=colors[i])
            # Add legend item for this series
            litems.append(LegendItem(label=s, renderers=[bars]))
            # Add hover tool
            # Note that toggleable is false because each HoverTool gets an icon in the toolbar if it can be toggled
            #  on and off. With large numbers of sections the toolbar is a real mess. For now just turn them off.
            # p.add_tools(HoverTool(tooltips=[(self._x_major_name, '@' + self._x_major_name),
            #                                 (self._x_minor_name, '{}'.format(s)),
            #                                 ("Total Hits", "@{ty}"),
            #                                 ("Hits/1000", "@{y}")],
            #                       renderers=[bars], toggleable=False,
            #                       point_policy='follow_mouse'))
            p.add_tools(HoverTool(tooltips=[(self._x_major_name, '@' + self._x_major_name),
                                            (self._x_minor_name, '{}'.format(s)),
                                            ("Total Hits", "@{Count}"),
                                            ("Hits/1000", "@{per1000}")],
                                  renderers=[bars], toggleable=False,
                                  point_policy='follow_mouse'))

        legend = Legend(items = litems, location=('center'))
        p.add_layout(legend, 'right')
        
        # Set axis titles
        p.xaxis.axis_label = x_title
        p.yaxis.axis_label = y_title
        p.xaxis.major_label_orientation = math.pi/4

        return p

    def create_display(self):
        """Create a display of the data. The display returned is a Boekh row with a
        data table on the left and a bar chart on the right. This may be displayed with
        Bokeh show().
        """
        # Create Bokeh datatable from self._display_data df
        # bokeh columns
        source=ColumnDataSource(self._df)
        Columns = [TableColumn(field=f, title=t) for f, t in zip(self._df.columns,
                                                                 self._column_display_names)
                                                            if t is not None]
        data_table = DataTable(columns=Columns,
                               source=source,
                               min_height=500, height_policy='auto',
                               index_position=None,
                               scroll_to_selection=True) # bokeh table

        # Create and display bar chart
        fig = self._create_plot(x_range=list(self._df[self._x_major_name].unique()),
                                s_data=source,
                                x_minor_values=self._df[self._x_minor_name].unique(),
                                colors=self._colors,
                                chart_title=None,
                                x_title=self._x_title,
                                y_title=self._y_title
                               )
        fig.min_border_left = 60
        msg = Div(text='<h4>{}</h4>'.format(self._title))
        r = layout([[msg], [data_table, fig]], sizing_mode='stretch_both')
        
        return r
