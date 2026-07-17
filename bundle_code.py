import os

def bundle_codes_with_structure(output_file="all_source_code.txt"):
    # Daftar folder utama yang ingin dipantau
    target_folders = ['app', 'scripts', 'config'] 
    # Ekstensi file yang relevan
    extensions = ('.py', '.env', '.gitignore', '.yaml', '.json', '.sql')
    # Folder yang wajib diabaikan agar file tidak raksasa
    ignored_folders = ['venv', '.git', '__pycache__', 'node_modules', '.vscode']

    with open(output_file, 'w', encoding='utf-8') as outfile:
        # Bagian 1: Tuliskan pohon direktori (Directory Tree) di paling atas
        outfile.write("STRUCTURE DIRECTORY:\n")
        outfile.write("="*50 + "\n")
        for folder in target_folders:
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if d not in ignored_folders]
                level = root.replace(folder, '').count(os.sep)
                indent = ' ' * 4 * (level)
                outfile.write(f"{indent}{os.path.basename(root)}/\n")
                subindent = ' ' * 4 * (level + 1)
                for f in files:
                    if f.endswith(extensions):
                        outfile.write(f"{subindent}{f}\n")
        
        outfile.write("\n" + "="*50 + "\n")
        outfile.write("FULL SOURCE CODE CONTENT:\n")
        outfile.write("="*50 + "\n\n")

        # Bagian 2: Tuliskan isi file satu per satu
        for folder in target_folders:
            if not os.path.exists(folder):
                continue
                
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if d not in ignored_folders]
                
                for file in files:
                    if file.endswith(extensions):
                        file_path = os.path.join(root, file)
                        
                        # Header File dengan Path Lengkap
                        outfile.write(f"{'#'*60}\n")
                        outfile.write(f"LOCATION: {file_path}\n")
                        outfile.write(f"{'#'*60}\n\n")
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8') as infile:
                                outfile.write(infile.read())
                        except Exception as e:
                            outfile.write(f"--- GAGAL MEMBACA FILE: {e} ---\n")
                        
                        outfile.write("\n\n")
    
    print(f"Berhasil! Silakan buka file: {output_file}")

if __name__ == "__main__":
    bundle_codes_with_structure()