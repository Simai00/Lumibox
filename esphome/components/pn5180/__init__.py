import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation, pins
from esphome.const import CONF_ID, CONF_TRIGGER_ID

AUTO_LOAD = []
DEPENDENCIES = []

pn5180_ns = cg.esphome_ns.namespace("pn5180")
PN5180Component = pn5180_ns.class_("PN5180Component", cg.PollingComponent)

CONF_CS_PIN = "cs_pin"
CONF_BUSY_PIN = "busy_pin"
CONF_RESET_PIN = "reset_pin"
CONF_ON_TAG = "on_tag"
CONF_ON_TAG_REMOVED = "on_tag_removed"

TagTrigger = pn5180_ns.class_("TagTrigger", automation.Trigger.template(cg.std_string))
TagRemovedTrigger = pn5180_ns.class_("TagRemovedTrigger", automation.Trigger.template())

CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(PN5180Component),
            cv.Required(CONF_CS_PIN): pins.internal_gpio_pin_number,
            cv.Required(CONF_BUSY_PIN): pins.internal_gpio_pin_number,
            cv.Required(CONF_RESET_PIN): pins.internal_gpio_pin_number,
            cv.Optional(CONF_ON_TAG): automation.validate_automation(
                {
                    cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(TagTrigger),
                }
            ),
            cv.Optional(CONF_ON_TAG_REMOVED): automation.validate_automation(
                {
                    cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(TagRemovedTrigger),
                }
            ),
        }
    )
    .extend(cv.polling_component_schema("250ms"))
)

async def to_code(config):
    cg.add_library("SPI", None)
    cg.add_library("https://github.com/ATrappmann/PN5180-Library.git", None)
    var = cg.new_Pvariable(
        config[CONF_ID],
        config[CONF_CS_PIN],
        config[CONF_BUSY_PIN],
        config[CONF_RESET_PIN],
    )
    await cg.register_component(var, config)

    for conf in config.get(CONF_ON_TAG, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        cg.add(var.register_tag_trigger(trigger))
        await automation.build_automation(trigger, [(cg.std_string, "x")], conf)

    for conf in config.get(CONF_ON_TAG_REMOVED, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        cg.add(var.register_tag_removed_trigger(trigger))
        await automation.build_automation(trigger, [], conf)