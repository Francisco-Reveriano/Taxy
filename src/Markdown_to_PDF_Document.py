import pypandoc
import tempfile
import os

def markdown_to_pdf(markdown_text: str, output_pdf_path: str) -> None:
    """
    Converts a Markdown string to a PDF file using Pandoc (via pypandoc).

    :param markdown_text: The raw Markdown content.
    :param output_pdf_path: Path (including filename) where the generated PDF should be saved.
    """
    # Create a temporary .md file
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".md", delete=False) as temp_md:
        temp_md.write(markdown_text)
        temp_md.flush()
        temp_md_path = temp_md.name

    try:
        # Use pypandoc to convert the temp Markdown file to PDF.
        # The 'pdf' target requires a working LaTeX installation.
        pypandoc.convert_file(
            source_file=temp_md_path,
            to="pdf",
            format="md",
            outputfile=output_pdf_path,
            extra_args=[
                # You can pass additional pandoc flags here:
                # e.g., "--pdf-engine=xelatex", "-V", "geometry:margin=1in"
            ],
        )
        print(f"✅ PDF successfully generated at: {output_pdf_path}")
    except RuntimeError as e:
        print("❌ Error during conversion:", e)
    finally:
        # Clean up the temporary Markdown file
        os.remove(temp_md_path)

def markdown_to_docx(markdown_text: str, output_docx_path: str) -> None:
    """
    Converts a Markdown string to a Word (.docx) file using Pandoc (via pypandoc).

    :param markdown_text: The raw Markdown content.
    :param output_docx_path: Path (including filename) where the generated .docx should be saved.
    """
    # Create a temporary .md file
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".md", delete=False) as temp_md:
        temp_md.write(markdown_text)
        temp_md.flush()
        temp_md_path = temp_md.name

    try:
        # Use pypandoc to convert the temp Markdown file to Word (.docx).
        pypandoc.convert_file(
            source_file=temp_md_path,
            to="docx",          # <- change “pdf” to “docx”
            format="md",
            outputfile=output_docx_path,
            extra_args=[
                # You can pass additional pandoc flags here, if needed.
                # e.g., ["-M", "title=My Document"] or similar metadata options.
            ],
        )
        print(f"✅ Word document successfully generated at: {output_docx_path}")
    except RuntimeError as e:
        print("❌ Error during conversion:", e)
    finally:
        # Clean up the temporary Markdown file
        os.remove(temp_md_path)