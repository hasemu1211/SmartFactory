# SmartFactory ArUco item candidates

- Dictionary: OpenCV `DICT_4X4_50`
- Candidate IDs: `20, 21, 22, 23, 24, 25, 26, 27, 28, 29`
- Marker square size: `40mm x 40mm` exactly
- Print setting: **100% / actual size**, no fit-to-page scaling
- Recommended print file: `aruco_4x4_50_item_candidates_20_29_a4_40mm.pdf`
- Existing map/zone IDs `0~12` are reserved and are not item candidates.

The marker itself is 40mm x 40mm. Labels and page whitespace are outside the marker square.
After printing, validate each candidate in the real global camera / ZoneROI crop and select the most stable IDs for MVP.
