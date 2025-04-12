import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import shutil

FAULT_FLAGS_V1 = [
    "batteryMinVoltage", "batteryMaxVoltage", "batteryAverageVoltage", "batteryVoltageDiff",
    "batteryTherm1Temp", "batteryTherm2Temp", "batteryTherm3Temp", "batteryCurrent"
]

FAULT_FLAGS_V2 = [
    "batteryMinVoltage", "batteryMaxVoltage", "batteryAverageVoltage", "batteryVoltageDiff",
    "batteryTherm1Temp", "batteryTherm2Temp", "batteryTherm3Temp", "batteryTherm4Temp", "batteryCurrent"
]

def decode_faults(fault_value, version):
    flags = FAULT_FLAGS_V1 if version == 1 else FAULT_FLAGS_V2
    fault_value = int(fault_value)
    return ", ".join([flag for i, flag in enumerate(flags) if (fault_value >> i) & 1]) or "clear"

def process_file(file_path):
    df = pd.read_csv(file_path, header=None)

    base_columns = ["Timestamp"] + [f"Cell_{i}" for i in range(1, 25)]
    therms_v1 = ["Therm_1", "Therm_2", "Therm_3"]
    therms_v2 = ["Therm_1", "Therm_2", "Therm_3", "Therm_4", "MOSFET_Temp", "Bot_Bal_Temp", "Top_Bal_Temp"]

    # Determine version by number of columns
    col_count = len(df.columns)
    version = 1 if col_count == 30 or col_count == 31 else 2

    if version == 1:
        columns = base_columns + therms_v1 + ["Current", "Faults"]
    else:
        columns = base_columns + therms_v2 + ["Current", "Faults"]

    df.columns = columns + [f"Extra_{i}" for i in range(len(df.columns) - len(columns))]

    # Convert cell voltages from mV to V
    df.iloc[:, 1:25] /= 10000.0

    # Compute total pack voltage
    df["Total_Voltage"] = df.iloc[:, 1:25].sum(axis=1)

    # Compute max absolute delta
    max_delta = df.iloc[:, 1:25].max(axis=1) - df.iloc[:, 1:25].min(axis=1)
    df["Delta"] = max_delta

    # Compute highest and lowest voltage cell indices
    df["Highest_Cell"] = df.iloc[:, 1:25].idxmax(axis=1).str.extract('(\\d+)').astype(int)
    df["Lowest_Cell"] = df.iloc[:, 1:25].idxmin(axis=1).str.extract('(\\d+)').astype(int)

    # Compute power (Total Voltage * Current)
    df["Power"] = df["Total_Voltage"] * df["Current"]

    # Highlight values
    df.loc[df["Delta"] > 0.03, "Delta_Highlight"] = "HIGH"
    df.loc[df["Power"] > 14000, "Power_Highlight"] = "HIGH"

    # Decode faults
    df["Fault_Text"] = df["Faults"].apply(lambda x: decode_faults(x, version))

    # Compute summary statistics
    temps = therms_v1 if version == 1 else therms_v2
    summary = {
        "Max Temperature": df[temps].max().max(),
        "Max Current": df["Current"].max(),
        "Max Power": df["Power"].max(),
        "Max Delta": df["Delta"].max(),
        "Max Cell Voltage": df.iloc[:, 1:25].max().max(),
        "Min Cell Voltage": df.iloc[:, 1:25].min().min(),
        "Mode Highest Cell": df["Highest_Cell"].mode().iloc[0],
        "Mode Lowest Cell": df["Lowest_Cell"].mode().iloc[0],
        "Present Faults": ", ".join(sorted(set(
            fault for faults in df["Fault_Text"] if faults != "clear" for fault in faults.split(", ")
        )))
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

    # Generate interactive plot
    fig = go.Figure()

    # Plot cell voltages
    for i in range(1, 25):
        fig.add_trace(go.Scatter(x=df.index, y=df[f"Cell_{i}"], mode='lines+markers', name=f"Cell_{i}"))

    # Add current line
    fig.add_trace(go.Scatter(x=df.index, y=df["Current"], mode='lines', name='Current (A)', yaxis="y2"))
    # Add power line
    fig.add_trace(go.Scatter(x=df.index, y=df["Power"], mode='lines', name='Power (W)', yaxis="y2"))

    # Highlight faults
    fault_indices = df.index[df["Fault_Text"] != "clear"].tolist()
    for idx in fault_indices:
        fig.add_vline(x=idx, line=dict(color="red", width=1, dash="dot"))

    fig.update_layout(
        title="Battery Cell Voltages, Current, and Power Over Time",
        xaxis_title="Index",
        yaxis=dict(title="Voltage (V)"),
        yaxis2=dict(title="Current / Power", overlaying="y", side="right"),
        legend=dict(x=1.05)
    )

    fig.write_html(os.path.join(output_dir, "cell_voltages_plot.html"))

    print(f"Processed data saved to {output_dir}")
    print(f"Summary saved to {output_dir}/battery_summary.csv")
    print(f"Interactive plot saved as {output_dir}/cell_voltages_plot.html")

# Prompt user for the folder containing CSV files
folder_path = input("Enter the folder path containing CSV files: ")

# Process all CSV files in the specified directory
for file in os.listdir(folder_path):
    if file.endswith(".csv"):
        process_file(os.path.join(folder_path, file))
