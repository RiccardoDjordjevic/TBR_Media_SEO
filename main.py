import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path


def load_keyword_data(file_path):
    """Load keyword data from CSV file."""
    print(f"Loading data from {file_path}...")
    try:
        df = pd.read_csv(file_path)
        print(f"Successfully loaded {len(df)} keywords with {len(df.columns)} attributes.")
        return df
    except Exception as e:
        print(f"Error loading file: {e}")
        return None


def clean_data(df):
    """Clean and prepare the keyword data."""
    print("Cleaning and preparing data...")

    # Make a copy to avoid warnings
    df_clean = df.copy()

    # Fix data types
    numeric_cols = ['Search Volume', 'Competition', 'CPC/USD', 'Estimated traffic amount', 'Visibility amount']
    for col in numeric_cols:
        if col in df_clean.columns:
            # Replace non-numeric values with NaN
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

    # Fill missing values
    for col in numeric_cols:
        if col in df_clean.columns:
            # Fill with 0 or appropriate value
            df_clean[col] = df_clean[col].fillna(0)

    # Create search intent flags (1 if yes, 0 if no)
    intent_cols = ['Informational Search Intent', 'Navigational Search Intent',
                   'Commercial Search Intent', 'Transactional Search Intent']

    for col in intent_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(lambda x: 1 if str(x).lower() == 'yes' else 0)

    print(f"Data cleaned. Shape: {df_clean.shape}")
    return df_clean


def calculate_keyword_score(df, weights=None):
    """
    Calculate a relevance score for each keyword based on multiple factors.

    Parameters:
    - df: DataFrame with keyword data
    - weights: Dictionary with weights for each factor

    Returns:
    - DataFrame with keywords and their scores
    """
    print("Calculating keyword scores...")

    # Default weights if none provided
    if weights is None:
        weights = {
            'search_volume': 0.30,  # Higher search volume is better
            'competition': -0.20,  # Lower competition is better (negative weight)
            'cpc': 0.15,  # Higher CPC indicates commercial value
            'traffic': 0.25,  # Higher estimated traffic is better
            'commercial_intent': 0.10  # Commercial/transactional intent is valuable
        }

    df_scored = df.copy()

    # Normalize factors between 0 and 1 to make them comparable
    if 'Search Volume' in df_scored.columns:
        max_sv = df_scored['Search Volume'].max()
        if max_sv > 0:
            df_scored['sv_normalized'] = df_scored['Search Volume'] / max_sv
        else:
            df_scored['sv_normalized'] = 0
    else:
        df_scored['sv_normalized'] = 0

    if 'Competition' in df_scored.columns:
        df_scored['comp_normalized'] = 1 - df_scored['Competition']  # Invert so lower is better
    else:
        df_scored['comp_normalized'] = 0

    if 'CPC/USD' in df_scored.columns:
        max_cpc = df_scored['CPC/USD'].max()
        if max_cpc > 0:
            df_scored['cpc_normalized'] = df_scored['CPC/USD'] / max_cpc
        else:
            df_scored['cpc_normalized'] = 0
    else:
        df_scored['cpc_normalized'] = 0

    if 'Estimated traffic amount' in df_scored.columns:
        max_traffic = df_scored['Estimated traffic amount'].max()
        if max_traffic > 0:
            df_scored['traffic_normalized'] = df_scored['Estimated traffic amount'] / max_traffic
        else:
            df_scored['traffic_normalized'] = 0
    else:
        df_scored['traffic_normalized'] = 0

    # Calculate commercial intent score
    commercial_cols = ['Commercial Search Intent', 'Transactional Search Intent']
    df_scored['commercial_intent_score'] = 0

    for col in commercial_cols:
        if col in df_scored.columns:
            df_scored['commercial_intent_score'] += df_scored[col]

    # Normalize commercial intent score
    max_intent = 2  # Maximum possible (sum of both intent types)
    df_scored['commercial_intent_score'] = df_scored['commercial_intent_score'] / max_intent

    # Calculate final weighted score
    df_scored['relevance_score'] = (
            weights['search_volume'] * df_scored['sv_normalized'] +
            weights['competition'] * df_scored['comp_normalized'] +
            weights['cpc'] * df_scored['cpc_normalized'] +
            weights['traffic'] * df_scored['traffic_normalized'] +
            weights['commercial_intent'] * df_scored['commercial_intent_score']
    )

    # Ensure scores are between 0 and 100 for readability
    min_score = df_scored['relevance_score'].min()
    max_score = df_scored['relevance_score'].max()

    if max_score > min_score:
        df_scored['relevance_score'] = 100 * (df_scored['relevance_score'] - min_score) / (max_score - min_score)

    # Add relevance category
    df_scored['relevance_category'] = pd.cut(
        df_scored['relevance_score'],
        bins=[0, 25, 50, 75, 100],
        labels=['Low', 'Medium', 'High', 'Very High']
    )

    return df_scored


def visualize_results(df_scored):
    """Create visualizations of the keyword analysis results."""
    print("Generating visualizations...")

    # Set the style
    sns.set(style="whitegrid")

    # Create a figure with multiple subplots
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))

    # 1. Top 15 Keywords by Relevance Score
    top_keywords = df_scored.sort_values('relevance_score', ascending=False).head(15)
    sns.barplot(x='relevance_score', y='Keyword', data=top_keywords, ax=axes[0, 0])
    axes[0, 0].set_title('Top 15 Keywords by Relevance Score')
    axes[0, 0].set_xlabel('Relevance Score')
    axes[0, 0].set_ylabel('Keyword')

    # 2. Distribution of Relevance Scores
    sns.histplot(df_scored['relevance_score'], bins=20, kde=True, ax=axes[0, 1])
    axes[0, 1].set_title('Distribution of Keyword Relevance Scores')
    axes[0, 1].set_xlabel('Relevance Score')
    axes[0, 1].set_ylabel('Count')

    # 3. Scatter Plot: Search Volume vs. Competition
    scatter = sns.scatterplot(
        x='Competition',
        y='Search Volume',
        size='CPC/USD',
        hue='relevance_score',
        palette='viridis',
        data=df_scored,
        ax=axes[1, 0]
    )
    axes[1, 0].set_title('Search Volume vs. Competition')
    axes[1, 0].set_xlabel('Competition (lower is better)')
    axes[1, 0].set_ylabel('Search Volume')

    # 4. Count by Relevance Category
    sns.countplot(x='relevance_category', data=df_scored, ax=axes[1, 1])
    axes[1, 1].set_title('Keywords by Relevance Category')
    axes[1, 1].set_xlabel('Relevance Category')
    axes[1, 1].set_ylabel('Count')

    # Adjust layout and save
    plt.tight_layout()

    return fig


def analyze_keywords_by_topic(df_scored):
    """Analyze keywords by topic/group to identify valuable niches."""
    print("Analyzing keywords by topic...")

    # Group by the 'Group' column if it exists
    if 'Group' in df_scored.columns:
        topic_analysis = df_scored.groupby('Group').agg({
            'relevance_score': 'mean',
            'Search Volume': 'sum',
            'Keyword': 'count',
            'Competition': 'mean',
            'CPC/USD': 'mean'
        }).sort_values('relevance_score', ascending=False)

        topic_analysis.columns = [
            'Avg Relevance Score',
            'Total Search Volume',
            'Number of Keywords',
            'Avg Competition',
            'Avg CPC'
        ]

        return topic_analysis
    else:
        print("No 'Group' column found for topic analysis.")
        return None


def export_results(df_scored, topic_analysis=None):
    """Export the analysis results to CSV files."""
    print("Exporting results...")

    # Create output directory if it doesn't exist
    output_dir = Path('keyword_analysis_results')
    output_dir.mkdir(exist_ok=True)

    # Export scored keywords
    scored_keywords_file = output_dir / 'tuscany_bike_route_keyword_scores.csv'
    columns_to_export = [
        'Keyword', 'Group', 'Search Volume', 'Competition', 'CPC/USD',
        'Estimated traffic amount', 'relevance_score', 'relevance_category'
    ]

    # Only include columns that exist in the DataFrame
    export_cols = [col for col in columns_to_export if col in df_scored.columns]

    # Sort by relevance score and export
    df_scored.sort_values('relevance_score', ascending=False)[export_cols].to_csv(
        scored_keywords_file, index=False
    )

    # Export topic analysis if available
    if topic_analysis is not None:
        topic_analysis_file = output_dir / 'tuscany_bike_route_topic_analysis.csv'
        topic_analysis.to_csv(topic_analysis_file)

    print(f"Results exported to {output_dir}")

    return str(output_dir)


def get_recommendations(df_scored, topic_analysis=None):
    """Generate strategic recommendations based on the analysis."""
    print("Generating recommendations...")

    recommendations = []

    # 1. Top Keywords Recommendation
    top_keywords = df_scored.sort_values('relevance_score', ascending=False).head(10)
    recommendations.append("TOP 10 PRIORITY KEYWORDS:")
    for i, (_, row) in enumerate(top_keywords.iterrows(), 1):
        keyword = row['Keyword']
        score = row['relevance_score']
        search_vol = row.get('Search Volume', 'N/A')
        recommendations.append(f"{i}. {keyword} (Score: {score:.1f}, Search Volume: {search_vol})")

    # 2. Topic Recommendations
    if topic_analysis is not None and not topic_analysis.empty:
        recommendations.append("\nTOP 5 KEYWORD TOPICS/GROUPS:")
        top_topics = topic_analysis.head(5)
        for i, (topic, row) in enumerate(top_topics.iterrows(), 1):
            score = row['Avg Relevance Score']
            volume = row['Total Search Volume']
            count = row['Number of Keywords']
            recommendations.append(f"{i}. {topic} (Avg Score: {score:.1f}, Total Volume: {volume}, Keywords: {count})")

    # 3. Low-Competition Opportunities
    low_comp_high_vol = df_scored[
        (df_scored['Competition'] < 0.4) &
        (df_scored['Search Volume'] > df_scored['Search Volume'].median())
        ].sort_values('relevance_score', ascending=False).head(5)

    if not low_comp_high_vol.empty:
        recommendations.append("\nLOW-COMPETITION OPPORTUNITIES:")
        for i, (_, row) in enumerate(low_comp_high_vol.iterrows(), 1):
            keyword = row['Keyword']
            comp = row['Competition']
            search_vol = row.get('Search Volume', 'N/A')
            recommendations.append(f"{i}. {keyword} (Competition: {comp:.2f}, Search Volume: {search_vol})")

    # 4. High Commercial Intent Keywords
    if 'commercial_intent_score' in df_scored.columns:
        high_commercial = df_scored[
            df_scored['commercial_intent_score'] > 0.5
            ].sort_values('relevance_score', ascending=False).head(5)

        if not high_commercial.empty:
            recommendations.append("\nHIGH COMMERCIAL INTENT KEYWORDS:")
            for i, (_, row) in enumerate(high_commercial.iterrows(), 1):
                keyword = row['Keyword']
                score = row['relevance_score']
                recommendations.append(f"{i}. {keyword} (Relevance Score: {score:.1f})")

    # 5. General Strategy Recommendation
    recommendations.append("\nRECOMMENDED STRATEGY:")
    recommendations.append("- Focus content creation on the top 10 priority keywords")
    recommendations.append("- Create topic clusters around the top 5 keyword groups")
    recommendations.append("- Target low-competition keywords for quick wins")
    recommendations.append("- Use high commercial intent keywords on conversion pages")
    recommendations.append("- Regularly update analysis as rankings and search volumes change")

    return "\n".join(recommendations)


def main():
    """Main function to run the keyword analysis."""
    # File path
    file_path = 'keywords01.csv'

    # Load and prepare data
    df = load_keyword_data(file_path)
    if df is None:
        return

    df_clean = clean_data(df)

    # Calculate keyword scores
    df_scored = calculate_keyword_score(df_clean)

    # Analyze by topic
    topic_analysis = analyze_keywords_by_topic(df_scored)

    # Visualize results
    fig = visualize_results(df_scored)

    # Export results
    output_dir = export_results(df_scored, topic_analysis)

    # Generate recommendations
    recommendations = get_recommendations(df_scored, topic_analysis)

    # Save recommendations to file
    recommendations_file = Path(output_dir) / 'tuscany_bike_route_recommendations.txt'
    with open(recommendations_file, 'w') as f:
        f.write(recommendations)

    # Save visualization
    fig_path = Path(output_dir) / 'tuscany_bike_route_keyword_analysis.png'
    fig.savefig(fig_path)

    print("\nAnalysis complete! Results saved to:", output_dir)
    print("\nKEY RECOMMENDATIONS:")
    print("\n".join(recommendations.split("\n")[:15]) + "\n...")


if __name__ == "__main__":
    main()