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

column_names = [
    "Timestamp",
    *[f"Cell_IC0_{i}" for i in range(1, 13)],
    *[f"Cell_IC1_{i}" for i in range(1, 13)],
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

    summary = {
        "Max Temp": df[therm_columns].max().max(),
        "Max Current": df["Current"].max(),
        "Max Power": df["Power"].max(),
        "Max Delta": df["Delta"].max(),
        "Max Cell Voltage": df.iloc[:, 1:25].max().max(),
        "Min Cell Voltage": df.iloc[:, 1:25].min().min(),
        "Mode Highest Cell": df["Highest_Cell"].mode().iloc[0],
        "Mode Lowest Cell": df["Lowest_Cell"].mode().iloc[0],
        "Present Faults": df["Fault_Text"].value_counts().to_dict(),
    }
    summary_df = pd.DataFrame(summary, index=["Summary"])

    # Create output folder based off the file name
    folder_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.join(os.path.dirname(file_path), folder_name)
    os.makedirs(output_dir, exist_ok=True)

    # Move original file to the folder
    shutil.move(file_path, os.path.join(output_dir, os.path.basename(file_path)))

    # Save processed data to excel with summary sheet
    with pd.ExcelWriter(
        os.path.join(output_dir, "processed_battery_data.xlsx")
    ) as writer:
        df.to_excel(writer, sheet_name="Data", index=False)
        summary_df.to_excel(writer, sheet_name="Summary")

        # Highlight faults in the data sheet
    #     workbook = writer.book
    #     worksheet = writer.sheets["Data"]
    #     yellow_fill = workbook.add_format({"bg_color": "#FBE921"})  # type: ignore
    #     red_fill = workbook.add_format({"bg_color": "#FF0000"})  # type: ignore
    #     for row_num, value in enumerate(df["Delta_Highlight"], start=2):
    #         if value == "HIGH":
    #             worksheet.set_row(row_num - 1, cell_format=yellow_fill)
    #     for row_num, value in enumerate(df["Power_Highlight"], start=2):
    #         if value == "HIGH":
    #             worksheet.set_row(row_num - 1, cell_format=yellow_fill)
    #     for row_num, value in enumerate(df["Fault_Text"], start=2):
    #         if value != "None":
    #             worksheet.set_row(row_num - 1, cell_format=red_fill)
    # print(f"Summary saved to {output_dir}/battery_summary.csv")

    display = go.Figure()

    # Cell voltage lines
    for i in range(1, 25):
        cell_name = f"Cell_IC0_{i}" if i < 13 else f"Cell_IC1_{i-12}"
        # rainbow colors for cells so 0 is red and 24 is purple
        display.add_trace(
            go.Scatter(
                x=df["Timestamp"],
                y=df[cell_name],
                mode="lines",
                name=cell_name,
                line=dict(color=f"hsl({(i-1)*15}, 70%, 50%)")
            )
        )
        # TODO: Change back to raw cell nums

    # Add current line
    display.add_trace(
        go.Scatter(
            x=df["Timestamp"],
            y=df["Current"],
            mode="lines",
            name="Current (A)",
            yaxis="y2",
        )
    )
    # Add power line
    display.add_trace(
        go.Scatter(
            x=df["Timestamp"], y=df["Power"], mode="lines", name="Power (W)", yaxis="y3"
        )
    )

    # Highlight faults
    fault_indices = df.index[df["Fault_Text"] != "None"].tolist()
    label_levels = [0.72, 0.78, 0.84, 0.9, 0.96]
    for i, idx in enumerate(fault_indices):
        fault_label = str(df["Fault_Text"].iloc[idx])
        y_pos = label_levels[i % len(label_levels)] + random.uniform(-0.012, 0.012)
        y_pos = max(0.65, min(0.98, y_pos))
        display.add_vline(
            x=df["Timestamp"].iloc[idx],
            line=dict(color="red", width=1, dash="dot"),
        )
        display.add_annotation(
            x=df["Timestamp"].iloc[idx],
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

    # Add labels
    display.update_layout(
        title="Battery Cell Voltages, Current, and Power Over Time",
        xaxis_title="Index",
        yaxis=dict(title="Voltage (V)"),
        yaxis2=dict(title="Current (A)", overlaying="y", side="right"),
        yaxis3=dict(title="Power (W)", overlaying="y", side="right", position=0.95),
        legend=dict(x=1.05),
    )
    display.write_html(os.path.join(output_dir, "battery_plot.html"))
    print(f"Interactive plot saved as {output_dir}/battery_plot.html")

    print(f"Processed data saved to {output_dir}")


def main():
    # Prompt user for the folder containing CSV files
    # folder_path = input("Enter the folder path containing CSV files: ")
    folder_path = "."
    for filename in os.listdir(folder_path):
        if filename.endswith(".csv"):
            file_path = os.path.join(folder_path, filename)
            print(f"Processing {file_path}...")
            process_file(file_path)


if __name__ == "__main__":
    main()
