/**
 * A mixin that can be used by a field grid component. It introduces the props that
 * will be passed by the GridViewField component and it created methods that are
 * going to be called.
 */
export default {
  props: {
    /**
     * Contains the field type object. Because each field type can have different
     * settings you need this in order to render the correct component or implement
     * correct validation.
     */
    field: {
      type: Object,
      required: true,
    },
    /**
     * The value of the grid field, this could for example for a number field 10,
     * text field 'Random string' etc.
     */
    value: {
      type: [String, Number, Object, Boolean],
      required: false,
    },
    /**
     * Indicates if the grid field is in a selected state.
     */
    selected: {
      type: Boolean,
      required: true,
    },
  },
  methods: {
    /**
     * Method that is called when the column is selected. For example when clicked
     * on the field. This is the moment to register event listeners if they are needed.
     */
    select() {},
    /**
     * Method that is called when the column is unselected. For example when clicked
     * outside the field. This is the moment to remove any event listeners.
     */
    beforeUnSelect() {},
    /**
     * Method that is called when the column is double clicked. Some grid fields want
     * to do something here apart from triggering the selected state. A boolean
     * toggles its value for example.
     */
    doubleClick() {},
    /**
     * There are keyboard shortcuts to select the next or previous field. For
     * example when the arrow or tab keys are pressed. The GridViewField component
     * first asks if this is allowed by calling this function. If false is returned
     * the next field is not going to be selected.
     */
    canSelectNext() {
      return true
    },
    /**
     * If the user presses ctrl/cmd + c while a field is selected, the value is
     * going to be copied to the clipboard. In some cases, for example when the user
     * is editing the value, we do not want to copy the value. If false is returned
     * the value won't be copied.
     */
    canCopy() {
      return true
    },
    /**
     * If the user presses ctrl/cmd + v while a field is selected, the value is
     * overwritten with the data of the clipboard. In some cases, for example when the
     * user is editing the value, we do not want to change the value. If false is
     * returned the value won't be changed.
     */
    canPaste() {
      return true
    },
    /**
     * If the user presses delete or backspace while a field is selected, the value is
     * deleted. In some cases, for example when the user is editing the value, we do
     * not want to delete the value. If false is returned the value won't be changed.
     */
    canEmpty() {
      return true
    },
  },
}
