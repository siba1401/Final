import streamlit as st
import pandas as pd
import numpy as np
import io

st.title("\U0001F4D8 Student Exam Failure & Simulation Report")

uploaded_file = st.file_uploader("Upload Exam CSV File", type=["csv"])

if uploaded_file:
    uploaded_file.seek(0)
    raw_df = pd.read_csv(uploaded_file, header=None)

    header_row_idx = raw_df[raw_df.apply(lambda row: row.astype(str).str.contains("Add.ID").any(), axis=1)].index[0]
    subject_row = raw_df.iloc[header_row_idx].fillna(method='ffill')
    component_row = raw_df.iloc[header_row_idx + 1].fillna("")
    columns = pd.MultiIndex.from_arrays([subject_row.values, component_row.values])
    raw_df.columns = columns

    df = raw_df.drop(index=list(range(header_row_idx + 2))).reset_index(drop=True)

    total_marks_row_idx = df[df.apply(lambda row: row.astype(str).str.contains(r'\d+\s*marks', case=False).any(), axis=1)].index
    if not total_marks_row_idx.empty:
        total_marks_row = df.loc[total_marks_row_idx[0]]
        df = df.drop(index=total_marks_row_idx[0]).reset_index(drop=True)
    else:
        total_marks_row = pd.Series(dtype=object)

    total_marks_dict = {}
    total_marks_table = []

    for (subject, component), value in total_marks_row.items():
        if pd.isna(value):
            continue
        try:
            value_str = str(value).strip()
            mark = int(value_str.split()[0])
            subject = subject.strip()
            component = component.strip()
            key1 = f"{component}_{subject}"
            key2 = f"{subject}_{component}"
            total_marks_dict[key1] = mark
            total_marks_dict[key2] = mark
            total_marks_table.append({"Subject": subject, "Component": component, "Total Marks": mark})
        except Exception:
            continue

    if total_marks_table:
        st.subheader("\U0001F4CB Total Marks for Each Subject Component")
        st.dataframe(pd.DataFrame(total_marks_table), use_container_width=True)

    df.columns = [f"{component.strip()}_{subject.strip()}" if component else subject.strip() for subject, component in df.columns]

    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col], errors='ignore')
        except:
            continue

    tee_cols = [col for col in df.columns if col.startswith("TEE_")]
    ica_cols = [col for col in df.columns if col.startswith("ICA_")]
    final_cols = [col for col in df.columns if "Final" in col]
    id_cols = [col for col in df.columns if 'Add.ID' in col or 'Student' in col]
    percent_df = df[id_cols].copy()
    has_percent_data = False

    for col in tee_cols:
        if col in total_marks_dict and total_marks_dict[col] != 0:
            percent_df[f"{col}_Percent"] = pd.to_numeric(df[col], errors='coerce') / total_marks_dict[col] * 100
            percent_df[col] = pd.to_numeric(df[col], errors='coerce')
            has_percent_data = True

    if has_percent_data:
        st.subheader("\U0001F4CA TEE% per Subject")
        st.dataframe(percent_df, use_container_width=True)

        st.subheader("\U0001F3AF Apply Grace Marks to Students with TEE% Between 37% and 39%")
        added_marks = st.slider("Grace Marks to be added to TEE:", 1, 15, 3)

        all_results = []
        grouped = df.groupby(df[id_cols[0]])

        for student_id, group in grouped:
            passed_all = True
            student_results = {id_cols[0]: student_id, "Got_Grace": False}
            graced_subjects = set()

            for col in tee_cols:
                subject = col.replace("TEE_", "")
                tee = pd.to_numeric(group[col].values[0], errors='coerce')
                total_tee = total_marks_dict.get(col, 100)
                tee_percent = tee / total_tee * 100 if total_tee else 0
                ica_col = f"ICA_{subject}"
                ica = pd.to_numeric(group[ica_col].values[0], errors='coerce') if ica_col in group else 0

                final_col = next((c for c in df.columns if ("Final_Marks" in c or "Final Marks" in c) and subject in c), None)
                final_score = pd.to_numeric(group[final_col].values[0], errors='coerce') if final_col else 0

                if 37 <= tee_percent <= 39:
                    tee += added_marks
                    tee_percent = tee / total_tee * 100 if total_tee else 0
                    graced_subjects.add(subject)
                    student_results["Got_Grace"] = True

                if total_tee == 100:
                    final_calc = (tee / 2) + ica
                elif total_tee == 50:
                    final_calc = tee + ica
                else:
                    final_calc = np.nan

                tee_pass = tee_percent >= 40
                final_pass = final_calc >= 40
                passed = tee_pass and final_pass
                passed_all = passed_all and passed

                tee_val = f"**{round(tee_percent, 2)}**" if subject in graced_subjects else round(tee_percent, 2)
                final_val = f"**{round(final_calc, 2)}**" if subject in graced_subjects else round(final_calc, 2)

                student_results[subject + "_TEE%"] = tee_val
                student_results[subject + "_Final"] = final_val
                student_results[subject + "_Status"] = "✅" if passed else "❌"

            student_results["Overall_Status"] = "✅ Pass" if passed_all else "❌ Fail"
            all_results.append(student_results)

        result_df = pd.DataFrame(all_results)

        passed_with_grace_df = result_df[(result_df["Got_Grace"]) & (result_df["Overall_Status"] == "✅ Pass")]

        passed_with_grace_df[id_cols[0]] = passed_with_grace_df.apply(
            lambda row: f"**{row[id_cols[0]]}**", axis=1
        )

        passed_with_grace_df.drop(columns=["Got_Grace"], inplace=True)

        st.subheader("📄 Passed Students (After Grace Marks)")
        st.dataframe(passed_with_grace_df, use_container_width=True)

    else:
        st.info("ℹ️ No valid TEE data to display percentages.")
