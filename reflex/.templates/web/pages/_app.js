import { ChakraProvider, extendTheme } from "@chakra-ui/react";
import { Global, css } from "@emotion/react";
import { useContext, useReducer } from "react";
import theme from "/utils/theme";
import { clientStorage, initialEvents, initialState, DispatchContext, StateContext, EventLoopContext } from "/utils/context.js";
import { applyDelta, useEventLoop } from "utils/state";

import '../styles/tailwind.css'

const GlobalStyles = css`
  /* Hide the blue border around Chakra components. */
  .js-focus-visible :focus:not([data-focus-visible-added]) {
    outline: none;
    box-shadow: none;
  }
`;

function EventLoopProvider({ children }) {
  const dispatch = useContext(DispatchContext)
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
      <DispatchContext.Provider value={dispatch}>
        {children}
      </DispatchContext.Provider>
    </StateContext.Provider>
  )
}

function MyApp({ Component, pageProps }) {
  return (
    <ChakraProvider theme={extendTheme(theme)}>
      <Global styles={GlobalStyles} />
      <StateProvider>
        <EventLoopProvider>
          <Component {...pageProps} />
        </EventLoopProvider>
      </StateProvider>
    </ChakraProvider>
  );
}

export default MyApp;
