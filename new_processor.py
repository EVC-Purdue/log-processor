# highlight+description fault, add min/max + delta volts collumns, total V, power, highlight over 14kw
# Summary sheet, list all faults w/ times, overall max/min/avg volts, max current, max power
# look for log proccesser in github for plotting library
# plot all cel voltages, current etc., add failt signifier

# time(ms), 24x cell voltages, therm1, therm2, therm3, therm4, thermFET, thermBalBot, thermBalTop, current, batteryMinVoltage, batteryMaxVoltage, batteryAverageVoltage, batteryVoltageDiff, batteryTherm1Temp, batteryTherm2Temp, batteryTherm3Temp, batteryTherm4Temp, batteryCurrent, overPower, coreZeroWatch

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import random
import shutil
import webbrowser
import tkinter as tk
from tkinter import filedialog

column_names = [
    "Timestamp",
    *[f"Cell_{i}" for i in range(1, 25)],
    "Therm_1",
    "Therm_2",
    "Therm_3",
    "Therm_4",
    "MOSFET_Temp",
    "Bot_Bal_Temp",
    "Top_Bal_Temp",
    "Current",
    "Faults",
]
fault_flags = [
    "batteryMinVoltage",
    "batteryMaxVoltage",
    "batteryAverageVoltage",
    "batteryVoltageDiff",
    "batteryTherm1Temp",
    "batteryTherm2Temp",
    "batteryTherm3Temp",
    "batteryTherm4Temp",
    "batteryCurrent",
    "currentOffset",
    "overPower",
    "coreZeroWatch",
]
therm_columns = [
    "Therm_1",
    "Therm_2",
    "Therm_3",
    "Therm_4",
    "MOSFET_Temp",
    "Bot_Bal_Temp",
    "Top_Bal_Temp",
]


def prompt_generate_overflow_cleaned(file_name: str, overflow_rows: int) -> bool:
    while True:
        response = input(
            f"Detected {overflow_rows} row(s) in {file_name} with a cell voltage over 6V. "
            "Generate overflow cleaned secondary files? (y/n): "
        ).strip().lower()
        if response in {"y", "yes"}:
            return True
        if response in {"n", "no"}:
            return False
        print("Please answer with 'y' or 'n'.")


def save_outputs(df_to_save: pd.DataFrame, output_dir: str, suffix: str = ""):
    excel_name = f"processed_battery_data{suffix}.xlsx"
    plot_name = f"battery_plot{suffix}.html"

    summary = {
        "Max Temp": df_to_save[therm_columns].max().max(),
        "Max Current": df_to_save["Current"].max(),
        "Max Power": df_to_save["Power"].max(),
        "Max Delta": df_to_save["Delta"].max(),
        "Max Cell Voltage": df_to_save.iloc[:, 1:25].max().max(),
        "Min Cell Voltage": df_to_save.iloc[:, 1:25].min().min(),
        "Mode Highest Cell": df_to_save["Highest_Cell"].mode().iloc[0],
        "Mode Lowest Cell": df_to_save["Lowest_Cell"].mode().iloc[0],
        "Present Faults": df_to_save["Fault_Text"].value_counts().to_dict(),
    }
    summary_df = pd.DataFrame(summary, index=["Summary"])

    with pd.ExcelWriter(os.path.join(output_dir, excel_name)) as writer:
        df_to_save.to_excel(writer, sheet_name="Data", index=False)
        summary_df.to_excel(writer, sheet_name="Summary")

    display = go.Figure()

    for i in range(1, 25):
        display.add_trace(
            go.Scatter(
                x=df_to_save["Timestamp"],
                y=df_to_save[f"Cell_{i}"],
                mode="lines",
                name=f"Cell_{i}",
                line=dict(color=f"hsl({(i-1)*15}, 70%, 50%)"),
            )
        )

    display.add_trace(
        go.Scatter(
            x=df_to_save["Timestamp"],
            y=df_to_save["Current"],
            mode="lines",
            name="Current (A)",
            yaxis="y2",
        )
    )

    display.add_trace(
        go.Scatter(
            x=df_to_save["Timestamp"],
            y=df_to_save["Power"],
            mode="lines",
            name="Power (W)",
            yaxis="y3",
        )
    )

    fault_indices = df_to_save.index[df_to_save["Fault_Text"] != "None"].tolist()
    label_levels = [0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5]
    for i, idx in enumerate(fault_indices):
        fault_label = str(df_to_save["Fault_Text"].iloc[idx])
        y_pos = label_levels[i % len(label_levels)]
        y_pos = max(0.65, min(0.98, y_pos))
        display.add_vline(
            x=df_to_save["Timestamp"].iloc[idx],
            line=dict(color="red", width=1, dash="dot"),
        )
        display.add_annotation(
            x=df_to_save["Timestamp"].iloc[idx],
            y=y_pos,
            xref="x",
            yref="paper",
            text=fault_label,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(size=9, color="red"),
            bgcolor="rgba(255,255,255,0.6)",
        )

    title_suffix = " (Overflow Cleaned)" if suffix else ""
    display.update_layout(
        title=f"Battery Cell Voltages, Current, and Power Over Time{title_suffix}",
        xaxis_title="Index",
        yaxis=dict(title="Voltage (V)"),
        yaxis2=dict(title="Current (A)", overlaying="y", side="right"),
        yaxis3=dict(title="Power (W)", overlaying="y", side="right", position=0.95),
        legend=dict(x=1.05),
    )
    display.write_html(os.path.join(output_dir, plot_name))


def decode_faults(fault_value):
    fault_value = str(fault_value).strip()
    output = []
    for i, char in enumerate(fault_value):
        if i >= len(fault_flags):
            break
        if char == "1":
            output.append(fault_flags[i])
    if not output:
        return "None"
    return ", ".join(output)


def process_file(file_path: str):
    df = pd.read_csv(file_path, header=None)
    df.columns = column_names + [  # add extra columns if present
        f"UNKNOWN_{i}" for i in range(len(df.columns) - len(column_names))
    ]

    # Subtract initial timestamp from all timestamps to start at 0
    df["Timestamp"] = df["Timestamp"] - df["Timestamp"].iloc[0]
    df["Timestamp"] = df["Timestamp"] / 1000.0

    # Convert cell voltages from mV to V
    cell_columns = column_names[1:25]
    df[cell_columns] = df[cell_columns].astype(float) / 10000.0

    # Compute total pack voltage
    df["Total_Voltage"] = df.iloc[:, 1:25].sum(axis=1)

    # Compute max absolute delta
    max_delta = df.iloc[:, 1:25].max(axis=1) - df.iloc[:, 1:25].min(axis=1)
    df["Delta"] = max_delta

    # Compute highest and lowest voltage cell indices
    df["Highest_Cell"] = (
        df.iloc[:, 1:25].idxmax(axis=1).str.extract(r"(\d+)").astype(int)
    )
    df["Lowest_Cell"] = (
        df.iloc[:, 1:25].idxmin(axis=1).str.extract(r"(\d+)").astype(int)
    )

    # Compute power (Total Voltage * Current)
    df["Power"] = df["Total_Voltage"] * df["Current"]

    # Highlight values
    df.loc[df["Delta"] > 0.03, "Delta_Highlight"] = "HIGH"
    df.loc[df["Power"] > 14000, "Power_Highlight"] = "HIGH"

    # Decode faults
    df["Fault_Text"] = df["Faults"].apply(decode_faults)

    # Create output folder based off the file name
    folder_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.join(os.path.dirname(file_path), folder_name)
    os.makedirs(output_dir, exist_ok=True)

    # Move original file to the folder
    shutil.move(file_path, os.path.join(output_dir, os.path.basename(file_path)))

    save_outputs(df, output_dir)
    print(f"Interactive plot saved as {output_dir}/battery_plot.html")

    overflow_mask = (df[cell_columns] > 6.0).any(axis=1)
    overflow_count = int(overflow_mask.sum())
    if overflow_count > 0:
        should_generate = prompt_generate_overflow_cleaned(
            os.path.basename(file_path), overflow_count
        )
        if should_generate:
            cleaned_df = df.loc[~overflow_mask].copy()
            if cleaned_df.empty:
                print(
                    "All rows exceeded the 6V threshold; no overflow cleaned files were generated."
                )
            else:
                save_outputs(cleaned_df, output_dir, suffix=" overflow cleaned")
                print(
                    f"Overflow cleaned files saved as {output_dir}/processed_battery_data overflow cleaned.xlsx "
                    f"and {output_dir}/battery_plot overflow cleaned.html"
                )

    print(f"Processed data saved to {output_dir}")


def main():
    # Open a folder picker so logs can be selected from Explorer.
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder_path = filedialog.askdirectory(title="Select folder containing log CSV files")
    root.destroy()

    if not folder_path:
        print("No folder selected. Exiting.")
        return

    # Run from the selected directory.
    os.chdir(folder_path)

    for filename in os.listdir(folder_path):
        if filename.endswith(".csv"):
            file_path = os.path.join(folder_path, filename)
            print(f"Processing {file_path}...")
            process_file(file_path)


if __name__ == "__main__":
    main()
