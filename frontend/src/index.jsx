import React, { useState, useEffect, createContext, useContext, useMemo } from 'react'
import { createRoot } from 'react-dom/client'
import axios from 'axios'
import { DateTime } from 'luxon'
import { Buffer } from 'buffer'
import styled from 'styled-components'
import { XCircle, Check2Circle, Triangle } from '@styled-icons/bootstrap'
import useAsyncEffect from 'use-async-effect'

const rootUrl = '/api'

const OkIcon = styled(Check2Circle)`
    color: green;
`
const NotOkIcon = styled(XCircle)`
    color: red;
`
const HiveIcon = styled(Triangle)`
    background: ${props => props.color};
    color: white;
    padding: .1em;
    border-radius: .25em;
`
const Root = styled.div`
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
    * { font-size: 110%; }
    h1 { font-size: 200%; }
    h2, h3 { font-size: 125%; }
`
const TitleBox = styled.div`
    box-shadow: 2px 2px 4px gray;
`
const Title = styled.h1`
    text-align: center;
`
const Subtitle = styled.h3`
    display: flex;
    flex-direction: column;
    align-items: center;
`
const EntryListing = styled.div`
    margin: 1em 0 .5em 0;
    display: flex;
    flex-direction: row;
    justify-content: space-around;
`
const EntryBox = styled.div`
    box-shadow: 1px 1px 2px lightgray;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: .5rem;
`
const Name = styled.h3`
    margin: 0;
    padding: 0;
    text-align: center;
`
const Description = styled.p`
    margin: 0;
    padding: 0;
    font-style: italic;
`
const Params = styled.dl`
    display: grid;
    grid-template-columns: 2fr 3fr;
`
const Param = styled.dt`
    text-align: center;
`
const Value = styled.dd`
    text-align: right;
`
const ImageBox = styled.div`
    display: flex;
    justify-content: center;
    img {
        width: auto;
        height: auto;
    }
`

const Table = ({ hives }) => {
    const entries = hives.map(({ name, description, color, nectar, workers, directions }) =>
        <Entry
            key={ name }
            name={ name }
            color={ color }
            nectar={ nectar }
            description={ description }
            workers={ workers }
            directions={ directions }
        />
    )
    return <EntryListing>{ ...entries }</EntryListing>
}
const Entry = ({ name, color, nectar, description, workers, directions }) => {
    return <EntryBox>
        <Name>{ name } <HiveIcon size=".75rem" color={ color } /></Name>
        <Description>{ description }</Description>
        <Params>
            <Param>Nectar</Param><Value>{ nectar.toFixed(2) }</Value>
            <Param>Workers</Param><Value>{ workers.total } (active: { workers.active })</Value>
            <Param>Default Radius</Param><Value>{ directions.default.radius.toFixed(2) }</Value>
            <Param>Default Linger</Param><Value>{ directions.default.linger.toFixed(2) }</Value>
            <Param>Ordered Radius</Param><Value>{ directions.ordered?.radius?.toFixed(2) }</Value>
            <Param>Ordered Linger</Param><Value>{ directions.ordered?.linger?.toFixed(2) }</Value>
        </Params>
    </EntryBox>
}
const Image = ({ plot }) => <ImageBox>
    <img width="auto" height="auto" src={`data:image/png;base64,${plot}`} />
</ImageBox>

const Header = () => {
    const { status, lastUpdated } = useContext(ApiContext)
    return (
        <TitleBox>
            <Title>Colony Collapse <i>!</i></Title>
            <Subtitle>
                <span>API: { status ? <OkIcon size="1em" /> : <NotOkIcon size="1em" /> }</span>
                <span>Last Updated: { lastUpdated?.toLocaleString(DateTime.TIME_24_WITH_SECONDS) }</span>
            </Subtitle>
        </TitleBox>
    )
}
const Body = () => {
    const { setLastUpdated } = useContext(ApiContext)
    const [ plot, setPlot ] = useState(null)
    const [ hives, setHives ] = useState(null)

    useAsyncEffect(async () => {
        const callback = async () => {
            const [{ data: { hives } }, { data: plot } ] = await Promise.all([
                axios.get(`${rootUrl}/status`),
                axios.get(`${rootUrl}/plot`, { responseType: 'arraybuffer' }),
            ])
            setHives(hives)
            setPlot(Buffer.from(plot, 'binary').toString('base64'))
            setLastUpdated(DateTime.now())
            timeout = setTimeout(callback, 1000)
        }
        var timeout = setTimeout(callback, 0)
        return () => clearTimeout(timeout)
    }, [])

    const table = useMemo(() =>
        hives && <Table hives={ hives } />
    , [ hives ])

    const image = useMemo(() =>
        plot && <Image plot={ plot } />
    , [ plot ])

    return <>{ table }{ image }</>
}

const ApiContext = createContext()
const App = ({ children }) => {
    const [ status, setStatus ] = useState(undefined)
    const [ lastUpdated, setLastUpdated ] = useState(undefined)

    useAsyncEffect(
        async isMounted => {
            const { status } = await axios.get(`${rootUrl}/test`)
            setStatus(status == 200)
            setLastUpdated(DateTime.now())
        },
        [ setStatus, setLastUpdated ],
    )

    return <Root>
        <ApiContext.Provider value={{ status, setStatus, lastUpdated, setLastUpdated }}>
            <Header />
            <Body />
        </ApiContext.Provider>
    </Root>
}

createRoot(
   document.getElementById('root')
).render(<App />)
