def make_table(pdf, data: list[list[str]]):
    line_height = pdf.font_size
    col_widths = [1.5 * pdf.epw / len(data[0])] + [
        pdf.epw / (1 + len(data[0])) for c in data[0]
    ]
    for row in data:
        for datum, col_width in zip(row, col_widths):
            pdf.multi_cell(
                col_width,
                line_height,
                datum,
                border=1,
                new_x="RIGHT",
                new_y="TOP",
                max_line_height=pdf.font_size,
            )
        pdf.ln(line_height)
