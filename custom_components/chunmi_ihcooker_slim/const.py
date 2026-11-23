"""Constants for the Chunmi IH Cooker Slim local integration."""

from __future__ import annotations

DOMAIN = "chunmi_ihcooker_slim"

MANUFACTURER = "CHUNMI"
MODEL = "chunmi.ihcooker.slim"
DEFAULT_NAME = "Chunmi IH Cooker Slim"

CONF_HOST = "host"
CONF_TOKEN = "token"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_USER_ID = "user_id"
CONF_INFORMATION = "information"

DEFAULT_SCAN_INTERVAL = 10
DEFAULT_TIMEOUT = 5
DEFAULT_USER_ID = "uid_homeassistant"
DEFAULT_INFORMATION = "info_030c01"

MIN_SCAN_INTERVAL = 2
MAX_SCAN_INTERVAL = 3600
MIN_TIMEOUT = 1
MAX_TIMEOUT = 30

DATA_COORDINATOR = "coordinator"
DATA_DEVICE = "device"
DATA_INFO = "info"
DATA_RECIPES = "recipes"
DATA_ACTIVE_RECIPE_ID = "active_recipe_id"
DATA_RECIPE_QUERY = "recipe_query"
DATA_SELECTED_PRESET = "selected_preset"
SERVICES_REGISTERED = "_services_registered"

ATTR_DEVICE_ID = "device_id"

SERVICE_START_PRESET = "start_preset"
PRESET_METHOD_BUILT_IN = "built_in"
PRESET_METHOD_RECIPE = "recipe"
DERIVED_APP_STATUS = "app_status"

# Recipe library services.
SERVICE_SEARCH_RECIPES = "search_recipes"
SERVICE_GET_RECIPE = "get_recipe"
SERVICE_START_RECIPE = "start_recipe"
SERVICE_ADD_FAVORITE = "add_favorite"
SERVICE_REMOVE_FAVORITE = "remove_favorite"
SERVICE_LIST_FAVORITES = "list_favorites"
SERVICE_REFRESH_RECIPES = "refresh_recipes"
SERVICE_SET_RECIPE_LANGUAGE = "set_recipe_language"
SERVICE_TRANSLATE_RECIPE = "translate_recipe"

ATTR_RECIPE = "recipe"
ATTR_QUERY = "query"
ATTR_LIMIT = "limit"
ATTR_FAVORITES_ONLY = "favorites_only"
ATTR_LANGUAGE = "language"

CONF_RECIPE_SOURCE = "recipe_source"
DEFAULT_RECIPE_SOURCE = "cache"
RECIPE_SOURCE_CACHE = "cache"
RECIPE_SOURCE_API = "api"
RECIPE_SOURCE_JSON = "json"

RECIPE_LANGUAGE_HA = "ha"
RECIPE_LANGUAGE_ORIGINAL = "original"
DEFAULT_RECIPE_LANGUAGE = RECIPE_LANGUAGE_HA

PLATFORMS = (
    "sensor",
    "binary_sensor",
    "switch",
    "number",
    "button",
    "text",
    "select",
)

# --- MIoT properties -------------------------------------------------------
# Keys are used as the "did" in miIO get_properties/set_properties calls.
PROP_STATUS = "status"                    # siid 2, piid 1
PROP_FAULT = "fault"                      # siid 2, piid 2
PROP_LEFT_TIME = "left_time"              # siid 2, piid 5
PROP_WORKING_TIME = "working_time"        # siid 2, piid 6
PROP_HEAT_LEVEL = "heat_level"            # siid 2, piid 7
PROP_COOK_MODE = "cook_mode"              # siid 2, piid 8 (absent on 2.2.0_0005)

PROP_MENU = "menu"                        # siid 3, piid 1
PROP_PHASE = "phase"                      # siid 3, piid 2
PROP_WORK_STATUS = "work_status"          # siid 3, piid 3
PROP_COOK_TIME = "cook_time"              # siid 3, piid 4
PROP_APPOINT_TIME = "appoint_time"        # siid 3, piid 5
PROP_PAUSE_TIME = "pause_time"            # siid 3, piid 6
PROP_TEMPERATURE = "temperature"          # siid 3, piid 7
PROP_TARGET_TEMPERATURE = "target_temperature"  # siid 3, piid 8
PROP_FIRE_GEARS = "fire_gears"            # siid 3, piid 9
PROP_STEP_TIME = "step_time"              # siid 3, piid 10
PROP_VERSION = "version"                  # siid 3, piid 11
PROP_CUSTOM_DETAILS = "custom_details"    # siid 3, piid 13
PROP_ERROR_CODE = "error_code"            # siid 3, piid 14
PROP_RECIPE_TYPE = "recipe_type"          # siid 3, piid 15
PROP_STEP_FLAG = "step_flag"              # siid 3, piid 16
PROP_FINISH_PUSH = "finish_push"          # siid 3, piid 24
PROP_BUZZER_MARK = "buzzer_mark"          # siid 3, piid 25
PROP_CHARGE_PHASE = "charge_phase"        # siid 3, piid 27
PROP_FINISH = "finish"                    # siid 3, piid 28
PROP_MOVE_TEMPERATURE = "move_temperature"  # siid 3, piid 29
PROP_STEP_TOTAL_TIME = "step_total_time"  # siid 3, piid 30

# Full mapping. Unsupported entries are kept so that other firmware versions
# can use them without a code change; read_properties() simply skips a -4001.
PROPERTIES: dict[str, dict[str, int]] = {
    PROP_STATUS: {"siid": 2, "piid": 1},
    PROP_FAULT: {"siid": 2, "piid": 2},
    PROP_LEFT_TIME: {"siid": 2, "piid": 5},
    PROP_WORKING_TIME: {"siid": 2, "piid": 6},
    PROP_HEAT_LEVEL: {"siid": 2, "piid": 7},
    PROP_COOK_MODE: {"siid": 2, "piid": 8},
    PROP_MENU: {"siid": 3, "piid": 1},
    PROP_PHASE: {"siid": 3, "piid": 2},
    PROP_WORK_STATUS: {"siid": 3, "piid": 3},
    PROP_COOK_TIME: {"siid": 3, "piid": 4},
    PROP_APPOINT_TIME: {"siid": 3, "piid": 5},
    PROP_PAUSE_TIME: {"siid": 3, "piid": 6},
    PROP_TEMPERATURE: {"siid": 3, "piid": 7},
    PROP_TARGET_TEMPERATURE: {"siid": 3, "piid": 8},
    PROP_FIRE_GEARS: {"siid": 3, "piid": 9},
    PROP_STEP_TIME: {"siid": 3, "piid": 10},
    PROP_VERSION: {"siid": 3, "piid": 11},
    PROP_CUSTOM_DETAILS: {"siid": 3, "piid": 13},
    PROP_ERROR_CODE: {"siid": 3, "piid": 14},
    PROP_RECIPE_TYPE: {"siid": 3, "piid": 15},
    PROP_STEP_FLAG: {"siid": 3, "piid": 16},
    PROP_FINISH_PUSH: {"siid": 3, "piid": 24},
    PROP_BUZZER_MARK: {"siid": 3, "piid": 25},
    PROP_CHARGE_PHASE: {"siid": 3, "piid": 27},
    PROP_FINISH: {"siid": 3, "piid": 28},
    PROP_MOVE_TEMPERATURE: {"siid": 3, "piid": 29},
    PROP_STEP_TOTAL_TIME: {"siid": 3, "piid": 30},
}

# Verified readable on firmware 2.2.0_0005.
SUPPORTED_PROPERTIES = frozenset(
    {
        PROP_STATUS,
        PROP_FAULT,
        PROP_LEFT_TIME,
        PROP_WORKING_TIME,
        PROP_HEAT_LEVEL,
        PROP_MENU,
        PROP_PHASE,
        PROP_WORK_STATUS,
        PROP_COOK_TIME,
        PROP_APPOINT_TIME,
        PROP_PAUSE_TIME,
        PROP_TEMPERATURE,
        PROP_TARGET_TEMPERATURE,
        PROP_FIRE_GEARS,
        PROP_STEP_TIME,
        PROP_VERSION,
        PROP_CUSTOM_DETAILS,
        PROP_ERROR_CODE,
        PROP_RECIPE_TYPE,
        PROP_STEP_FLAG,
        PROP_FINISH_PUSH,
        PROP_BUZZER_MARK,
        PROP_CHARGE_PHASE,
        PROP_FINISH,
        PROP_MOVE_TEMPERATURE,
        PROP_STEP_TOTAL_TIME,
    }
)

# Verified writable on firmware 2.2.0_0005.
WRITABLE_PROPERTIES = frozenset(
    {PROP_HEAT_LEVEL, PROP_FINISH_PUSH, PROP_BUZZER_MARK}
)
# These two reject integer writes with -4005 and require real JSON booleans.
BOOLEAN_PROPERTIES = frozenset({PROP_FINISH_PUSH, PROP_BUZZER_MARK})

# --- MIoT actions ----------------------------------------------------------
ACTION_START_COOK = "start_cook"                    # 2-1
ACTION_CANCEL_COOKING = "cancel_cooking"            # 2-2
ACTION_PAUSE = "pause"                              # 2-3
ACTION_START_COOKING = "start_cooking"              # 3-1
ACTION_PAUSE_COOKING = "pause_cooking"              # 3-2
ACTION_PAUSE_RECOVER = "pause_recover"              # 3-3
ACTION_CANCEL_COOKING_V2 = "cancel_cooking_v2"      # 3-4
ACTION_SET_MENU = "set_menu"                        # 3-5
ACTION_DELETE_MENU = "delete_menu"                  # 3-6
ACTION_CONTINUE_COOKING = "continue_cooking"        # 3-7
ACTION_NEXT_STEP_COOKING = "next_step_cooking"      # 3-8
ACTION_FACTORY_RESET = "factory_reset"              # 3-9
ACTION_SET_CHARGE = "set_charge"                    # 3-10
ACTION_GET_ERROR_RECORDED = "get_error_recorded"    # 3-11
ACTION_GET_SELFCHECK = "get_selfcheck"              # 3-12

ACTIONS: dict[str, tuple[int, int]] = {
    ACTION_START_COOK: (2, 1),
    ACTION_CANCEL_COOKING: (2, 2),
    ACTION_PAUSE: (2, 3),
    ACTION_START_COOKING: (3, 1),
    ACTION_PAUSE_COOKING: (3, 2),
    ACTION_PAUSE_RECOVER: (3, 3),
    ACTION_CANCEL_COOKING_V2: (3, 4),
    ACTION_SET_MENU: (3, 5),
    ACTION_DELETE_MENU: (3, 6),
    ACTION_CONTINUE_COOKING: (3, 7),
    ACTION_NEXT_STEP_COOKING: (3, 8),
    ACTION_FACTORY_RESET: (3, 9),
    ACTION_SET_CHARGE: (3, 10),
    ACTION_GET_ERROR_RECORDED: (3, 11),
    ACTION_GET_SELFCHECK: (3, 12),
}

# Firmware 2.2.0_0005 does not accept plain values in a MIoT action's ``in``
# list.  Every entry must be an object with the argument's property id (piid)
# and a JSON value of the expected type.  The piids and types below come from
# the public MIoT spec and were confirmed in the firmware's action validators.
ACTION_ARGUMENT_PIIDS: dict[str, tuple[int, ...]] = {
    ACTION_START_COOK: (8,),                    # cook-mode
    ACTION_CANCEL_COOKING: (),
    ACTION_PAUSE: (),
    ACTION_START_COOKING: (22, 17, 19),         # recipe-name, cook-data, user-id
    ACTION_PAUSE_COOKING: (20, 19),             # information, user-id
    ACTION_PAUSE_RECOVER: (20, 19),
    ACTION_CANCEL_COOKING_V2: (20, 19),
    ACTION_SET_MENU: (17, 19, 21, 22),          # cook-data, user-id, bell, recipe-name
    ACTION_DELETE_MENU: (19, 20, 21, 23),       # user-id, information, bell, menu-order
    ACTION_CONTINUE_COOKING: (20, 19),
    ACTION_NEXT_STEP_COOKING: (20, 19),
    ACTION_FACTORY_RESET: (20, 19),
    ACTION_SET_CHARGE: (18,),                   # charge-data
    ACTION_GET_ERROR_RECORDED: (31,),           # error-recorded-index
    ACTION_GET_SELFCHECK: (34,),                # selfcheck-cmd
}

# Piids that the firmware validator requires to be JSON numbers.  Everything
# else in an action's ``in`` list must be a JSON string.
ACTION_INTEGER_ARGUMENTS = frozenset({8, 21, 23, 31, 34})

# Actions that accepted an empty ``in`` list on firmware 2.2.0_0005.
VERIFIED_ACTIONS = frozenset({ACTION_CANCEL_COOKING, ACTION_PAUSE})

# --- Value maps ------------------------------------------------------------
STATUS_MAP: dict[int, str] = {
    0: "idle",
    1: "cooking",
    2: "timing",
    3: "appointment",
    4: "paused",
    5: "shutdown",
}

# Entity states are always English. The custom card owns its own bilingual
# labels, so sensor states must not follow the Home Assistant display language.
APP_STATUS_MAP: dict[int, str] = {
    0: "idle",
    1: "cooking",
    2: "timing",
    3: "appointment",
    4: "paused",
    5: "shutdown",
}
APP_STATUS_ERROR = "fault"

WORK_STATUS_MAP: dict[int, str] = {
    1: "idle",
    2: "cooking",
    4: "appointment",
    8: "error",
    9: "idle_timing",
    10: "cooking_timing",
    11: "shutdown",
    12: "paused",
    14: "charging",
    18: "stop_cooking",
    19: "timing_pause",
}

FAULT_MAP: dict[int, str] = {
    0: "none",
    2: "no_pan",
    3: "high_voltage",
    4: "low_voltage",
    5: "bottom_sensor_overheat",
    7: "igbt_sensor_overheat",
    8: "igbt_sensor_fault",
    10: "bottom_sensor_fault",
    11: "communication_fault",
    12: "coil_open",
}

COOK_MODE_MAP: dict[int, str] = {
    1: "hotpot",
    2: "steam_boil",
    3: "simmer",
    4: "stir_fry",
    5: "deep_fry",
}

RECIPE_TYPE_MAP: dict[int, str] = {
    0: "official",
    1: "single_fire",
    2: "multi_fire",
    3: "single_temperature",
    4: "recipe",
    5: "single_recipe",
}

SELFCHECK_MAP: dict[int, str] = {
    1: "voltage",
    3: "sensor_ntc",
    4: "sensor_igbt",
    5: "communication",
}

ACTIVE_WORK_STATUSES = frozenset({2, 10})
PAUSED_WORK_STATUSES = frozenset({12, 19})
FAULTY_WORK_STATUSES = frozenset({8})

# Firmware uses 0 for success and 1 for refusal/no-effect. Treating 1 as
# success hides failed starts and menu writes.
SUCCESS_CODES = frozenset({0})

MIOT_ERROR_CODES: dict[int, str] = {
    -4001: "property is not readable on this firmware",
    -4002: "property is not writable on this firmware",
    -4003: "action or property does not exist on this firmware",
    -4004: "the device rejected the request",
    -4005: "invalid value or data type",
    -4006: "the device is busy",
    -4007: "the operation timed out",
}
