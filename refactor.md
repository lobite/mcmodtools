# Refactor To-Do

- Confine the ModrinthAPI class to actual API requests, other functions should go to utils
- Only fetch dependencies after the user has made choices about possibly incompatible mod versions
- Reduce redundant dictionary declarations
- Refactor the mod dictionary to a class
- Merge get_versions with resolve_conflict
- Reconsider how mod versions are evaluated against the target game version

## Version Conflicts

Cases:

Case 1: A mod version exists for the target game version
- The latest mod version is "release" for the target game version. -> quietly continue
- There is a release mod version for the target game version, but a newer alpha/beta is available. -> prompt
- There is no release available for the target game version, but alpha/beta are available. -> prompt/warn (user preference?)

Case 2: There is no mod version for the target game version
- but there is a release mod version for older game versions.
- but there is a alpha/beta mod version for older game versions.

Case 3:

- There are no mod versions available for fabric.