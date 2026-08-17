"""Application stylesheet."""

APP_STYLESHEET = """
QWidget {
    background: #17191d;
    color: #e8e8e8;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow { background: #111318; }
QWidget#mainSidebar {
    background: #111318;
    border-right: 1px solid #2c3038;
}
QListWidget#mainNavigation {
    background: #111318;
    border: 0;
    padding: 16px 8px;
    outline: 0;
}
QListWidget#mainNavigation::item {
    border-radius: 6px;
    margin: 3px 0;
    padding: 12px 14px;
    color: #b8bdc7;
}
QListWidget#mainNavigation::item:selected {
    background: #323845;
    color: #ffffff;
}
QLabel#pageTitle { font-size: 19pt; font-weight: 650; color: #ffffff; }
QLabel#placeholderTitle { font-size: 16pt; font-weight: 600; }
QLabel#fieldLabel { color: #c9ced8; font-weight: 600; }
QLabel#pageHint { color: #a7adb8; }
QWidget#versionBadgeRow {
    background: transparent;
}
QLabel#versionBadge {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #2d3441, stop: 1 #202630);
    border: 1px solid #3a4656;
    border-radius: 11px;
    color: #d5deea;
    font-weight: 600;
    padding: 5px 10px;
}
QLabel#versionBadge[kind="profile"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #383249, stop: 1 #292535);
    border-color: #534873;
    color: #dcd6f0;
}
QLabel#versionBadge[kind="current"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #294047, stop: 1 #1b2a30);
    border-color: #3f606b;
    color: #cbeaf5;
}
QLabel#versionStatusBadge {
    border-radius: 11px;
    font-weight: 700;
    padding: 5px 10px;
}
QLabel#versionStatusBadge[syncState="match"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #285239, stop: 1 #1a3124);
    border: 1px solid #4f966b;
    color: #bbf0ce;
}
QLabel#versionStatusBadge[syncState="mismatch"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #5a3339, stop: 1 #382226);
    border: 1px solid #b55a64;
    color: #ffc0c7;
}
QLabel#versionStatusBadge[syncState="unknown"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #463d2d, stop: 1 #2d291f);
    border: 1px solid #847447;
    color: #e8d9ae;
}
QLabel#versionBadgeDetail {
    color: #87909e;
    padding-left: 2px;
}
QLabel#gameLocationWarning {
    background: #3a2923;
    border: 1px solid #8b5a3c;
    border-radius: 6px;
    color: #ffc898;
    margin: 8px;
    padding: 9px;
}
QLabel#catalogLoadWarning {
    background: #442326;
    border: 1px solid #a34f57;
    border-radius: 6px;
    color: #ffb6bc;
    margin: 8px;
    padding: 9px;
}
QLabel#gameFolderWarning { color: #f0a77b; }
QLabel#gameFolderConfirmed { color: #81d5aa; }
QLabel#lastExportedProfile { color: #78d9e8; font-weight: 650; }
QLabel#exportSectionTitle {
    color: #c8cfda;
    font-size: 10pt;
    font-weight: 650;
}
QFrame#exportSectionDivider {
    color: #343c4a;
    background: #343c4a;
    max-height: 1px;
}
QLabel#guideSectionTitle {
    color: #d4a843;
    font-size: 13pt;
    font-weight: 650;
}
QLabel#infoIcon {
    background: #2a303a;
    border: 1px solid #4b5568;
    border-radius: 8px;
    color: #c9d3e4;
    font-size: 8.5pt;
    font-weight: 700;
    min-width: 16px;
    min-height: 16px;
}
QLabel#infoIcon:hover {
    background: #374154;
    border-color: #6a7891;
    color: #e4ecf8;
}
QLabel#guideBody { color: #c9ced8; }
QLabel#matchHighlightLegend { color: #9eb5ca; padding-left: 2px; }
QToolButton#resistanceCapButton {
    background: #292e37;
    border: 1px solid #3d4654;
    border-radius: 6px;
    color: #d9e3ed;
    font-weight: 600;
    padding: 7px 16px;
}
QToolButton#resistanceCapButton:hover { background: #39404c; }
QToolButton#resistanceCapButton[active="true"] {
    background: #24575d;
    border-color: #52a9ad;
    color: #f2ffff;
}
QToolButton#resistanceCapButton[active="true"]:hover {
    background: #2c6870;
}
QFrame#resistanceCapBody {
    background: #1b2027;
    border: 1px solid #3a4654;
    border-radius: 6px;
}
QCheckBox#resistanceCapToggle {
    background: transparent;
    font-weight: 600;
    color: #edf3f7;
}
QCheckBox#resistanceCapToggle::indicator {
    width: 16px;
    height: 16px;
    background-color: #f4f7fa;
    border: 1px solid #ffffff;
    border-radius: 3px;
}
QCheckBox#resistanceCapToggle::indicator:hover {
    border-color: #8fe4e4;
}
QCheckBox#resistanceCapToggle::indicator:checked {
    background-color: #53aeb2;
    border: 2px solid #d9ffff;
}
QLabel#resistanceCapHint {
    background: transparent;
    color: #9eabb9;
    padding-bottom: 3px;
}
QLabel#weightLegend {
    background: #242831;
    border: 1px solid #343a46;
    border-radius: 6px;
    color: #c8cdd6;
    padding: 7px 10px;
}
QLineEdit#profileName {
    background: #22262d;
    border: 1px solid #3a404c;
    border-radius: 5px;
    padding: 7px 9px;
}
QLineEdit#profileName:focus { border-color: #d4a843; }
QLineEdit#profileInput {
    background: #242932;
    border: 1px solid #3a414d;
    border-radius: 5px;
    padding: 4px 9px;
}
QLineEdit#profileInput:focus { border-color: #d4a843; }
QPushButton#profileAction {
    background: #292e37;
    border: 1px solid #3a414d;
    border-radius: 5px;
    padding: 7px 13px;
}
QPushButton#profileAction:hover { background: #39404c; }
QLabel#profileStatusPill {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #383249, stop: 1 #292535);
    border: 1px solid #534873;
    border-radius: 11px;
    color: #dcd6f0;
    font-weight: 600;
    padding: 5px 10px;
}
QLabel#paletteStatus {
    border-radius: 8px;
    font-weight: 600;
    padding: 7px 10px;
}
QLabel#paletteStatus[dirty="true"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #5a4930, stop: 1 #382e20);
    border: 1px solid #b28a43;
    color: #f6d895;
}
QLabel#paletteStatus[dirty="false"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #285239, stop: 1 #1a3124);
    border: 1px solid #4f966b;
    color: #bbf0ce;
}
QTableWidget#topMatchesTable, QTableWidget#affixSlotTable,
QTableWidget#uniqueSlotTable, QTableWidget#addonSlotTable {
    background: #181b20;
    alternate-background-color: #1e2229;
    border: 1px solid #303540;
    gridline-color: #303540;
    selection-background-color: #3a4454;
}
QFrame#slotFilterBar, QFrame#typeFilterBar, QFrame#affixSlotRow,
QFrame#uniqueSlotRow, QFrame#addonSlotRow {
    background: #1b1e24;
    border: 1px solid #303640;
    border-radius: 6px;
}
QFrame#slotFilterDivider { color: #555d69; margin: 1px 5px; }
QLabel#weaponFilterWarning {
    background: #382f20;
    border: 1px solid #705b31;
    border-radius: 5px;
    color: #efcf84;
    padding: 7px 10px;
}
QLabel#affixCategoryTitle {
    color: #d4a843;
    font-size: 13pt;
    font-weight: 650;
    padding: 8px 2px 2px 2px;
}
QLabel#affixSlotName, QLabel#affixTableTitle {
    color: #eef0f4;
    font-weight: 600;
}
QCheckBox { spacing: 5px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QComboBox#minimumGradeSelector, QComboBox#profileSwapSelector {
    background: #242932;
    border: 1px solid #3a414d;
    border-radius: 5px;
    padding: 4px 9px;
}
QComboBox#profilePicker {
    background: #242932;
    border: 1px solid #3a414d;
    border-radius: 5px;
    padding: 4px 9px;
    min-width: 260px;
}
QComboBox#profilePicker[activeLoaded="true"] {
    background: #2b2837;
    border: 1px solid #534873;
    color: #dcd6f0;
}
QComboBox#minimumGradeSelector {
    min-width: 48px;
}
QComboBox#profileSwapSelector {
    min-width: 260px;
}
QComboBox#minimumGradeSelector QAbstractItemView,
QComboBox#profileSwapSelector QAbstractItemView,
QComboBox#profilePicker QAbstractItemView {
    background: #20242b;
    border: 1px solid #3a414d;
    selection-background-color: #3a4454;
}
QTabWidget#recommendationTabs::pane {
    border: 1px solid #303540;
    border-radius: 7px;
    background: #181b20;
}
QHeaderView::section {
    background: #252a32;
    color: #eef0f4;
    border: 0;
    border-right: 1px solid #343a46;
    padding: 7px;
}
QFrame#matchDetailPane {
    background: #20242b;
    border: 1px solid #343a46;
    border-radius: 5px;
}
QLabel#matchDetailTitle {
    border: 0;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #ffffff;
    font-size: 11pt;
    font-weight: 650;
    padding: 9px 12px;
}
QTextEdit#matchDetails {
    background: #20242b;
    border: 0;
    border-top: 1px solid #343a46;
    border-radius: 0;
    padding: 6px;
}
QSpinBox#matchLimit {
    background: #20242b;
    border: 1px solid #343a46;
    border-radius: 5px;
    padding: 6px;
}
QLineEdit#outputPath, QPlainTextEdit#outputPreview {
    background: #20242b;
    border: 1px solid #343a46;
    border-radius: 5px;
    padding: 7px;
}
QFrame#paletteSection {
    background: #1b1e24;
    border: 1px solid #303640;
    border-radius: 7px;
}
QComboBox#paletteSelector {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #2c333f, stop: 1 #20252d);
    border: 1px solid #3a414d;
    border-radius: 5px;
    padding: 6px 10px;
}
QComboBox#paletteSelector QAbstractItemView {
    background: #20242b;
    border: 1px solid #3a414d;
    selection-background-color: #3a4454;
}
QPushButton#primaryAction {
    background: #8f6b24;
    border: 1px solid #c59a3c;
    border-radius: 5px;
    color: #ffffff;
    font-weight: 600;
    padding: 9px 16px;
}
QPushButton#primaryAction:hover { background: #a77d2a; }
QPushButton#primaryAction:disabled { background: #343434; color: #777777; }
QTabWidget#profileTabs::pane {
    border: 1px solid #303540;
    border-radius: 7px;
    background: #181b20;
}
QTabBar::tab {
    background: #20242b;
    color: #aeb4bf;
    border: 1px solid #303540;
    border-bottom: 0;
    padding: 9px 18px;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #303642; color: #ffffff; }
QFrame#packageAccordion {
    border: 1px solid #303640;
    border-radius: 7px;
    background: #1b1e24;
}
QFrame#masteryPanel {
    background: #1b1e24;
    border: 1px solid #303640;
    border-radius: 7px;
}
QLabel#masteryTitle, QLabel#skillSectionTitle {
    color: #eef0f4;
    font-weight: 600;
}
QComboBox#masterySelector {
    background: #242932;
    border: 1px solid #3a414d;
    border-radius: 5px;
    padding: 6px 9px;
}
QComboBox#masterySelector::drop-down { border: 0; width: 24px; }
QComboBox#masterySelector QAbstractItemView {
    background: #20242b;
    border: 1px solid #3a414d;
    selection-background-color: #3a4454;
}
QListWidget#masterySkillList {
    background: #181b20;
    border: 1px solid #303540;
    border-radius: 5px;
    outline: 0;
}
QListWidget#masterySkillList::item { padding: 5px 7px; }
QListWidget#masterySkillList::item:selected {
    background: #3a4454;
    color: #ffffff;
}
QListWidget#masterySkillList::item:disabled {
    background: #1b1e24;
    color: #68707c;
}
QPushButton#skillAdd, QPushButton#skillRemove {
    background: #292e37;
    border: 1px solid #3a414d;
    border-radius: 5px;
    padding: 6px 11px;
}
QPushButton#skillAdd:hover, QPushButton#skillRemove:hover { background: #39404c; }
QPushButton#skillAdd:disabled { color: #626873; background: #202329; }
QFrame#skillWeightRow {
    background: #20242b;
    border: 1px solid #303640;
    border-radius: 5px;
}
QPushButton#packageHeader {
    background: #252a32;
    border: 0;
    border-radius: 6px;
    color: #eef0f4;
    font-weight: 600;
    padding: 10px 12px;
    text-align: left;
}
QPushButton#packageHeader:hover { background: #2c323c; }
QWidget#packageModifyControl { background: #252a32; }
QLabel#packageModifyLabel { color: #b8bec9; padding: 0 4px 0 8px; }
QWidget#packageBody { background: #1b1e24; }
QToolButton#conversionSourcesButton {
    color: #aeb8c6;
    padding: 3px 7px;
}
QToolButton#conversionSourcesButton:hover {
    background: #303640;
    border-radius: 4px;
    color: #ffffff;
}
QFrame#conversionSourcesBody {
    background: #171a1f;
    border-top: 1px solid #2b3039;
    border-bottom: 1px solid #2b3039;
}
QFrame#conversionSourcesBody QCheckBox { color: #c2c8d1; }
QToolButton#weightArrow {
    background: #292e37;
    border: 1px solid #3a414d;
    border-radius: 4px;
    min-width: 29px;
    min-height: 29px;
}
QToolButton#weightArrow:hover { background: #39404c; }
QToolButton#weightArrow:disabled { color: #545965; background: #202329; }
QToolButton#weightStar {
    background: transparent;
    border: 0;
    color: #686e79;
    font-size: 16pt;
    min-width: 22px;
    padding: 0;
}
QToolButton#weightStar[filled="true"] { color: #e0b44c; }
QToolButton#weightStar:hover { color: #f1ca6d; }
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: #17191d; width: 11px; }
QScrollBar::handle:vertical { background: #3a404b; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
