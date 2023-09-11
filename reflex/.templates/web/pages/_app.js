import { ChakraProvider, extendTheme } from "@chakra-ui/react";
import { Global, css } from "@emotion/react";
import { useReducer } from "react";
import theme from "/utils/theme";
import { clientStorage, initialEvents, initialState, StateContext, EventLoopContext } from "/utils/context.js";
import { applyDelta, useEventLoop } from "utils/state";

import '../styles/tailwind.css'

const GlobalStyles = css`
  /* Hide the blue border around Chakra components. */
  .js-focus-visible :focus:not([data-focus-visible-added]) {
    outline: none;
    box-shadow: none;
  }
`;

function EventLoopProvider({ dispatch, children }) {
  const [Event, connectError] = useEventLoop(
    dispatch,
    initialEvents,
    clientStorage,
  )
  return (
    <EventLoopContext.Provider value={[Event, connectError]}>
      {children}
    </EventLoopContext.Provider>
  )
}

function StateProvider({ children }) {
  const [state, dispatch] = useReducer(applyDelta, initialState)

  return (
    <StateContext.Provider value={state}>
      <EventLoopProvider dispatch={dispatch}>
        {children}
      </EventLoopProvider>
    </StateContext.Provider>
  )
}

function MyApp({ Component, pageProps }) {
  return (
    <ChakraProvider theme={extendTheme(theme)}>
      <Global styles={GlobalStyles} />
      <StateProvider>
        <Component {...pageProps} />
      </StateProvider>
    </ChakraProvider>
  );
}

export default MyApp;
