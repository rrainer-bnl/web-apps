import glob

print ("searching directories\n")

def search_files(directory, file_extension):
    search_pattern = f'{directory}/**/*{file_extension}'
    matching_files = glob.glob(search_pattern, recursive=True)
    return matching_files

# Example usage: Searching for Python files (.py) in the cohortA directory
directory_path = 'cohortA'
file_extension = '.py'
matching_files = search_files(directory_path, file_extension)

# Print the matching file paths
for file_path in matching_files:
    print(file_path)

