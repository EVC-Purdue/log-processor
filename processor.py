import pandas as pd
import plotly.express as px
import os
import shutil
import argparse

def process_file(file_path):
    df = pd.read_csv(file_path, header=None)
    
    # Assign column labels
    columns = ["Timestamp"] + [f"Cell_{i}" for i in range(1, 25)] + ["Therm_1", "Therm_2", "Therm_3", "Current"]
    df.columns = columns + [f"Extra_{i}" for i in range(len(df.columns) - len(columns))]  # Keep extra columns
    
    # Convert cell voltages from mV to V
    df.iloc[:, 1:25] /= 10000.0
    
    # Compute total pack voltage
    df["Total_Voltage"] = df.iloc[:, 1:25].sum(axis=1)
    
    # Compute max absolute delta
    max_delta = df.iloc[:, 1:25].max(axis=1) - df.iloc[:, 1:25].min(axis=1)
    df["Delta"] = max_delta
    
    # Compute highest and lowest voltage cell indices
    df["Highest_Cell"] = df.iloc[:, 1:25].idxmax(axis=1).str.extract('(\d+)').astype(int)
    df["Lowest_Cell"] = df.iloc[:, 1:25].idxmin(axis=1).str.extract('(\d+)').astype(int)
    
    # Compute power (Total Voltage * Current)
    df["Power"] = df["Total_Voltage"] * df["Current"]
    
    # Highlight values
    df.loc[df["Delta"] > 0.03, "Delta_Highlight"] = "HIGH"
    df.loc[df["Power"] > 14000, "Power_Highlight"] = "HIGH"
    
    # Compute summary statistics
    summary = {
        "Max Temperature": df[["Therm_1", "Therm_2", "Therm_3"]].max().max(),
        "Max Current": df["Current"].max(),
        "Max Power": df["Power"].max(),
        "Max Delta": df["Delta"].max(),
        "Max Cell Voltage": df.iloc[:, 1:25].max().max(),
        "Min Cell Voltage": df.iloc[:, 1:25].min().min(),
        "Mode Highest Cell": df["Highest_Cell"].mode()[0],
        "Mode Lowest Cell": df["Lowest_Cell"].mode()[0]
    }
    summary_df = pd.DataFrame(summary, index=["Summary"])
    
    # Create output folder
    folder_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.join(os.path.dirname(file_path), folder_name)
    os.makedirs(output_dir, exist_ok=True)
    
    # Move original file to the folder
    shutil.move(file_path, os.path.join(output_dir, os.path.basename(file_path)))
    
    # Save processed data
    df.to_csv(os.path.join(output_dir, "processed_battery_data.csv"), index=False)
    summary_df.to_csv(os.path.join(output_dir, "battery_summary.csv"))
    
    # Generate interactive plot of all cell voltages
    fig = px.line(df, x=df.index, y=[f"Cell_{i}" for i in range(1, 25)], title="Cell Voltages Over Time",
                  labels={"index": "Index", "value": "Voltage (V)"}, markers=True)
    fig.write_html(os.path.join(output_dir, "cell_voltages_plot.html"))
    
    print(f"Processed data saved to {output_dir}")
    print(f"Summary saved to {output_dir}/battery_summary.csv")
    print(f"Interactive plot saved as {output_dir}/cell_voltages_plot.html")

def main():
    parser = argparse.ArgumentParser(description="Process battery CSV files.")
    parser.add_argument("folder", help="Folder containing CSV files")
    args = parser.parse_args()
    
    for file in os.listdir(args.folder):
        if file.endswith(".csv"):
            process_file(os.path.join(args.folder, file))

if __name__ == "__main__":
    main()
