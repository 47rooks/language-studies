import pandas as pd

# Utility functions for text size data

def get_text_total_sizes():
    """Get the total words for each text in its entirety.
    Returns
      A dataframe with columns Text and 'Total Words'.
    """
    # Get the basic totals - using __ALL__ values
    size_data = pd.read_csv("../data/Text Sizes.csv")
    total_sizes = size_data.query('Section == \'__ALL__\'')[['Text','Total Words']].groupby(['Text']).sum()

    # Reset the index for a normal flat df.
    total_sizes.reset_index(inplace=True)

    return total_sizes

def get_author_total_sizes():
    """Get the total words for an author across all texts attributed to each author.
    Returns
      A dataframe with columns Author and 'Total Words'.
    """
    # Get the totals by Author summing from section totals only
    size_data = pd.read_csv("../data/Text Sizes.csv")
    author_sizes = size_data.query('Section != \'__ALL__\'')[['Author','Total Words']].groupby(['Author']).sum()

    # Reset the index for a normal flat df.
    author_sizes.reset_index(inplace=True)

    return author_sizes

def get_section_total_sizes():
    """Get the total words by Text/Section.
    Returns
      A dataframe with columns Text, Section and 'Total Words'.
    """
    # Get the section sizes removing the __ALL__ counts.
    size_data = pd.read_csv("../data/Text Sizes.csv")
    section_sizes = size_data.query('Section != \'__ALL__\'')[['Text', 'Section', 'Total Words']]

    return section_sizes

# Utility function for connective data

def compute_per1000_data(df):
    """Create a per1000 column which computes the ratio of hits per 1000 words
    for each text/section/connective row.
    
    FIXME - modify to handle Text vs Text/Section automatically
    """
    if 'Section' in df.columns and 'Text' in df.columns:
        conn = df[['Text', 'Section', 'Connective', 'Total']].groupby(['Text', 'Section', 'Connective']).sum()
        conn.reset_index(inplace=True)
        conn_with_totals = conn.join(get_section_total_sizes().set_index(['Text', 'Section']), on=['Text', 'Section'])
        conn_with_totals['per1000'] = conn_with_totals.Total / conn_with_totals['Total Words'] * 1000
    elif 'Text' in df.columns:
        conn = df[['Text', 'Connective', 'Total']].groupby(['Text', 'Connective']).sum()
        conn.reset_index(inplace=True)
        conn_with_totals = conn.join(get_section_total_sizes().set_index(['Text']), on=['Text'])
    else:
        # Assume here that df contains columns Total and 'Total Words' with whatever keys the caller wants
        conn_with_totals = df
        
    conn_with_totals['per1000'] = conn_with_totals.Total / conn_with_totals['Total Words'] * 1000

    return conn_with_totals
